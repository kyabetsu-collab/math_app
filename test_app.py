import streamlit as st
import json
import random
import pandas as pd
import numpy as np
import sympy as sp
import os
import unicodedata
import plotly.express as px
import time
from datetime import datetime
import glob

# ==============================
# 1. 設定・教科定義
# ==============================
SUBJECTS = ["数学", "英語", "国語", "理科", "社会"]
TEACHER_PASSWORD = "admin" 

REQUIRED_COLUMNS = [
    "student_id", "question", "student_answer", 
    "correct_answer", "is_correct", "timestamp"
]

# ==============================
# 2. データ管理ロジック
# ==============================

def get_problem_file():
    subject = st.session_state.get("selected_subject", "数学")
    return f"{subject}_problems.json"

def get_result_file():
    subject = st.session_state.get("selected_subject", "数学")
    return f"{subject}_results.csv"

def load_problems():
    path = get_problem_file()
    if not os.path.exists(path): return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_problems(problems):
    path = get_problem_file()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)

def load_results():
    path = get_result_file()
    if not os.path.exists(path):
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        df = pd.read_csv(path)
        if "is_correct" in df.columns:
            df["is_correct"] = pd.to_numeric(df["is_correct"], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def safe_save_results(new_df, path):
    max_retries = 5
    for i in range(max_retries):
        try:
            header = not os.path.exists(path)
            new_df.to_csv(path, mode='a', index=False, header=header, encoding='utf-8')
            return True
        except Exception:
            time.sleep(random.uniform(0.1, 0.3))
    return False

# --- 採点ロジック ---
def normalize_text(s):
    if not isinstance(s, str): return str(s)
    s = unicodedata.normalize("NFKC", s).strip().replace(" ", "")
    s = s.replace("，", ",").replace("√", "sqrt").replace("π", "pi")
    return s

def is_equal(student, correct):
    s_raw = normalize_text(student)
    c_raw = normalize_text(correct)
    if s_raw == c_raw: return True
    try:
        if abs(float(s_raw) - float(c_raw)) < 1e-7: return True
    except: pass
    try:
        s_expr = s_raw.replace("x=", "").replace("y=", "")
        c_expr = c_raw.replace("x=", "").replace("y=", "")
        diff = sp.simplify(f"({s_expr}) - ({c_expr})")
        if diff == 0: return True
    except: pass
    return False

# ==============================
# 3. 生徒用画面
# ==============================

def student_view():
    subject = st.session_state.selected_subject
    st.header(f"✏️ {subject} テスト")
    
    sid = st.text_input("生徒ID（出席番号や氏名）を入力")
    if not sid:
        st.info("IDを入力して開始してください")
        return

    problems = load_problems()
    if not problems:
        st.warning(f"{subject}の問題はまだ登録されていません。")
        return

    if "q_idx" not in st.session_state:
        st.session_state.q_idx = 0
        st.session_state.order = list(range(len(problems)))
        random.shuffle(st.session_state.order)
        st.session_state.answers_dict = {}
        st.session_state.done = False

    if st.session_state.done:
        st.success("解答を送信しました！")
        st.subheader("📝 あなたの採点結果")
        
        personal_res = []
        correct_count = 0
        for i in range(len(problems)):
            s_ans = st.session_state.answers_dict.get(i, "")
            correct_ans = problems[i]["answer"]
            judgment = "⭕" if is_equal(s_ans, correct_ans) else "❌"
            if judgment == "⭕": correct_count += 1
            personal_res.append({
                "問題": problems[i]["question"],
                "あなたの解答": s_ans,
                "正解": correct_ans,
                "結果": judgment
            })
        
        score = int((correct_count / len(problems)) * 100)
        st.metric("スコア", f"{score}%", f"{correct_count} / {len(problems)} 問正解")
        st.table(pd.DataFrame(personal_res))
        
        if st.button("メニューに戻る"):
            for key in ["q_idx", "order", "answers_dict", "done"]:
                if key in st.session_state: del st.session_state[key]
            st.session_state.mode = None
            st.rerun()
        return

    idx = st.session_state.order[st.session_state.q_idx]
    prob = problems[idx]
    st.subheader(f"問題 {st.session_state.q_idx + 1} / {len(problems)}")
    st.info(prob["question"])
    
    saved_val = st.session_state.answers_dict.get(idx, "")
    ans = st.text_input("答えを入力", value=saved_val, key=f"q_{st.session_state.q_idx}")

    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.q_idx > 0:
            if st.button("← 前へ"):
                st.session_state.answers_dict[idx] = ans
                st.session_state.q_idx -= 1
                st.rerun()
    with col2:
        is_last = (st.session_state.q_idx == len(problems) - 1)
        if st.button("採点・終了" if is_last else "次へ ➔"):
            st.session_state.answers_dict[idx] = ans
            if is_last:
                results = []
                for p_idx, p_data in enumerate(problems):
                    s_ans = st.session_state.answers_dict.get(p_idx, "")
                    is_c = 1 if is_equal(s_ans, p_data["answer"]) else 0
                    results.append({
                        "student_id": sid, "question": p_data["question"],
                        "student_answer": s_ans, "correct_answer": p_data["answer"],
                        "is_correct": is_c, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                if safe_save_results(pd.DataFrame(results), get_result_file()):
                    st.session_state.done = True
                st.rerun()
            else:
                st.session_state.q_idx += 1
                st.rerun()

# ==============================
# 4. 教師用画面
# ==============================

def teacher_view():
    subject = st.session_state.selected_subject
    st.header(f"🧑‍🏫 教師用管理（{subject}）")
    tab1, tab2, tab3 = st.tabs(["📊 成績分析・個人詳細", "📝 問題編集", "⚙️ データ管理"])

    df = load_results()

    with tab1:
        if df.empty:
            st.info("解答データがありません。")
        else:
            acc = df["is_correct"].mean() * 100
            c1, c2, c3 = st.columns(3)
            c1.metric("全体平均正答率", f"{acc:.1f}%")
            c2.metric("総解答データ数", len(df))
            c3.metric("受験人数", df["student_id"].nunique())
            
            st.divider()
            st.subheader("👤 生徒別成績一覧")
            student_stats = df.groupby("student_id").agg(
                正解数=("is_correct", "sum"),
                問題数=("is_correct", "count")
            ).reset_index()
            student_stats["正答率(%)"] = (student_stats["正解数"] / student_stats["問題数"] * 100).round(1)
            st.dataframe(student_stats.sort_values("正答率(%)", ascending=False), use_container_width=True)

            st.subheader("🔍 個別解答ログ")
            target = st.selectbox("詳細を見たい生徒を選択", ["--選択してください--"] + list(student_stats["student_id"].unique()))
            if target != "--選択してください--":
                st.table(df[df["student_id"] == target][["question", "student_answer", "correct_answer", "is_correct", "timestamp"]])

    with tab2:
        problems = load_problems()
        with st.expander("➕ 新規問題を追加"):
            nq = st.text_area("問題文")
            na = st.text_input("正解")
            if st.button("登録"):
                problems.append({"question": nq, "answer": na})
                save_problems(problems)
                st.rerun()
        
        for i, p in enumerate(problems):
            with st.expander(f"問{i+1}: {p['question'][:30]}..."):
                problems[i]["question"] = st.text_area("問題", p["question"], key=f"eq_{i}")
                problems[i]["answer"] = st.text_input("正解", p["answer"], key=f"ea_{i}")
                col_u, col_d = st.columns(2)
                if col_u.button("更新", key=f"u_{i}"):
                    save_problems(problems)
                    st.success("更新しました")
                if col_d.button("削除", key=f"d_{i}"):
                    problems.pop(i)
                    save_problems(problems)
                    st.rerun()

    with tab3:
        st.subheader("📦 成績データのアーカイブと削除")
        col_arch, col_del = st.columns(2)
        
        with col_arch:
            st.write("### アーカイブ（保存してリセット）")
            if st.button("📁 過去ログとして保存する"):
                path = get_result_file()
                if os.path.exists(path):
                    ts = datetime.now().strftime("%Y%m%d_%H%M")
                    new_path = path.replace(".csv", f"_{ts}.csv")
                    os.rename(path, new_path)
                    st.success(f"保存完了: {new_path}")
                    time.sleep(1)
                    st.rerun()
                else: st.warning("データがありません")

        with col_del:
            st.write("### 完全削除")
            if st.button("🗑️ 完全に消去する"):
                path = get_result_file()
                if os.path.exists(path):
                    os.remove(path)
                    st.success("削除しました")
                    time.sleep(1)
                    st.rerun()

        st.divider()
        st.subheader("📁 アーカイブ済みファイルの確認")
        # フォルダ内の過去ファイルを検索
        archive_files = glob.glob(f"{subject}_results_*.csv")
        if not archive_files:
            st.info("アーカイブされた過去のデータはありません。")
        else:
            selected_file = st.selectbox("過去のファイルを選択", archive_files)
            temp_df = pd.read_csv(selected_file)
            st.write(f"ファイル名: {selected_file}")
            st.download_button(label="📥 このCSVをダウンロード", data=temp_df.to_csv(index=False), file_name=selected_file, mime="text/csv")
            if st.checkbox("中身をプレビュー"):
                st.dataframe(temp_df)

# ==============================
# 5. メインロジック
# ==============================

st.set_page_config(page_title="総合学習分析アプリ", layout="wide")

if "mode" not in st.session_state: st.session_state.mode = None
if "selected_subject" not in st.session_state: st.session_state.selected_subject = "数学"

with st.sidebar:
    st.title("🍀 メニュー")
    if st.button("🏠 ホーム（教科選択）"):
        st.session_state.mode = None
        st.rerun()
    st.divider()
    st.subheader(f"教科: {st.session_state.selected_subject}")
    if st.button("✏️ 生徒用テスト"):
        st.session_state.mode = "student"
        st.rerun()
    if st.button("🧑‍🏫 教師用画面"):
        st.session_state.mode = "auth"
        st.rerun()

if st.session_state.mode is None:
    st.title("📚 総合学習分析アプリ")
    st.write("教科を選んでください。アーカイブ機能により過去の成績も安全に保管できます。")
    cols = st.columns(len(SUBJECTS))
    for i, sub in enumerate(SUBJECTS):
        with cols[i]:
            if st.button(sub, use_container_width=True):
                st.session_state.selected_subject = sub
                st.success(f"{sub} 選択中")
    st.info("サイドバーから「テスト」または「教師画面」へ進んでください。")

elif st.session_state.mode == "student":
    student_view()

elif st.session_state.mode == "auth":
    st.title("ログイン")
    pw = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        if pw == TEACHER_PASSWORD:
            st.session_state.mode = "teacher"
            st.rerun()
        else: st.error("不一致")

elif st.session_state.mode == "teacher":
    teacher_view()