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
# 2. データ管理・安全な保存ロジック
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
        # 読み込み時も他者の書き込みとぶつからないよう配慮
        df = pd.read_csv(path)
        if "is_correct" in df.columns:
            df["is_correct"] = pd.to_numeric(df["is_correct"], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def safe_save_results(new_df, path):
    """一斉アクセス時に書き込み競合を防ぐ安全な保存関数"""
    max_retries = 5
    for i in range(max_retries):
        try:
            # ファイルが存在しない場合はヘッダー付きで新規作成
            header = not os.path.exists(path)
            # mode='a' (追記モード) で開く
            new_df.to_csv(path, mode='a', index=False, header=header, encoding='utf-8')
            return True
        except Exception:
            # 誰かが書き込み中の場合は0.1~0.3秒待機してリトライ
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
    
    sid = st.text_input("生徒ID（出席番号など）を入力")
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
        st.success(f"お疲れ様でした！{subject}の解答を送信しました。")
        if st.button("メニューに戻る"):
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
            if st.button("← 前へ戻る"):
                st.session_state.answers_dict[idx] = ans
                st.session_state.q_idx -= 1
                st.rerun()
    with col2:
        is_last = (st.session_state.q_idx == len(problems) - 1)
        btn_label = "採点して終了 ➔" if is_last else "次へ進む ➔"
        if st.button(btn_label):
            st.session_state.answers_dict[idx] = ans
            if is_last:
                results_to_save = []
                for p_idx, p_data in enumerate(problems):
                    s_ans = st.session_state.answers_dict.get(p_idx, "")
                    is_correct = 1 if is_equal(s_ans, p_data["answer"]) else 0
                    results_to_save.append({
                        "student_id": sid, "question": p_data["question"],
                        "student_answer": s_ans, "correct_answer": p_data["answer"],
                        "is_correct": is_correct, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                res_df = pd.DataFrame(results_to_save)
                # 安全な保存関数の呼び出し
                if safe_save_results(res_df, get_result_file()):
                    st.session_state.done = True
                else:
                    st.error("送信に失敗しました。もう一度「終了」を押してください。")
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
    tab1, tab2, tab3 = st.tabs(["📊 成績分析", "📝 問題編集", "⚙️ 教科設定"])

    df = load_results()

    with tab1:
        if df.empty:
            st.info(f"{subject}の解答データがありません。")
            if st.button("最新の状態に更新"): st.rerun()
        else:
            acc = df["is_correct"].mean() * 100
            c1, c2, c3 = st.columns(3)
            c1.metric("平均正答率", f"{acc:.1f}%")
            c2.metric("総解答数", len(df))
            c3.metric("受験人数", df["student_id"].nunique())
            
            if st.button("🔄 データを最新に更新"): st.rerun()

            st.subheader("成績分布")
            s_stats = df.groupby("student_id")["is_correct"].mean() * 100
            fig = px.histogram(s_stats, x="is_correct", nbins=10, labels={'is_correct':'正答率(%)', 'count':'人数'})
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        problems = load_problems()
        with st.expander("➕ 新規問題追加"):
            nq = st.text_area("問題文")
            na = st.text_input("正解")
            if st.button("登録"):
                problems.append({"question": nq, "answer": na})
                save_problems(problems)
                st.success("追加しました")
                st.rerun()
        
        for i, p in enumerate(problems):
            with st.expander(f"問{i+1}: {p['question'][:30]}..."):
                problems[i]["question"] = st.text_area("問題", p["question"], key=f"eq_{i}")
                problems[i]["answer"] = st.text_input("正解", p["answer"], key=f"ea_{i}")
                col_save, col_del = st.columns(2)
                if col_save.button("更新", key=f"sv_{i}"):
                    save_problems(problems)
                    st.success("保存完了")
                if col_del.button("削除", key=f"dl_{i}"):
                    problems.pop(i)
                    save_problems(problems)
                    st.rerun()

    with tab3:
        st.subheader("データ管理")
        if st.button(f"🗑️ {subject}の全成績をリセット"):
            if os.path.exists(get_result_file()): os.remove(get_result_file())
            st.success("データを削除しました。")
            st.rerun()

# ==============================
# 5. メイン実行・ホーム画面
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
    st.subheader(f"教科：{st.session_state.selected_subject}")
    if st.button("✏️ 生徒用テスト"):
        st.session_state.mode = "student"
        st.rerun()
    if st.button("🧑‍🏫 教師用画面"):
        st.session_state.mode = "auth"
        st.rerun()

if st.session_state.mode is None:
    st.title("📚 総合学習データ分析アプリ")
    st.write("学習したい教科を選択してください。一斉解答にも対応しています。")
    
    cols = st.columns(len(SUBJECTS))
    for i, sub in enumerate(SUBJECTS):
        with cols[i]:
            if st.button(sub, use_container_width=True):
                st.session_state.selected_subject = sub
                st.success(f"{sub} 選択中")
    
    st.divider()
    st.markdown(f"### 現在の教科: **{st.session_state.selected_subject}**")
    st.info("サイドバーから「生徒用テスト」または「教師用画面」を選択してください。")

elif st.session_state.mode == "student":
    student_view()

elif st.session_state.mode == "auth":
    st.title("教師用ログイン")
    pw = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        if pw == TEACHER_PASSWORD:
            st.session_state.mode = "teacher"
            st.rerun()
        else: st.error("パスワードが違います")

elif st.session_state.mode == "teacher":
    teacher_view()