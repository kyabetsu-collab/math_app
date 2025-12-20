import streamlit as st
import json
import random
import pandas as pd
import numpy as np
import sympy as sp
import os
import unicodedata
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
    "correct_answer", "is_correct", "timestamp", "type"
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
        # Excel対応のためBOM付きUTF-8で読み込み
        df = pd.read_csv(path, encoding='utf-8-sig')
        if "is_correct" in df.columns:
            df["is_correct"] = pd.to_numeric(df["is_correct"], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def safe_save_results(new_df, path):
    """Excel対応(utf-8-sig)で保存"""
    max_retries = 5
    for i in range(max_retries):
        try:
            header = not os.path.exists(path)
            new_df.to_csv(path, mode='a', index=False, header=header, encoding='utf-8-sig')
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
        st.session_state.answers_dict = {}
        st.session_state.done = False

    if st.session_state.done:
        st.success("解答を送信しました！")
        if st.button("メニューに戻る"):
            for key in ["q_idx", "answers_dict", "done"]:
                if key in st.session_state: del st.session_state[key]
            st.session_state.mode = None
            st.rerun()
        return

    prob = problems[st.session_state.q_idx]
    st.subheader(f"問題 {st.session_state.q_idx + 1} / {len(problems)}")
    st.info(prob["question"])
    
    # --- 出題形式の分岐 ---
    q_type = prob.get("type", "記述式")
    if q_type == "選択式":
        ans = st.radio("正しいものを選択してください", prob.get("options", []), key=f"q_{st.session_state.q_idx}")
    else:
        ans = st.text_input("答えを入力してください", key=f"q_{st.session_state.q_idx}")

    if st.button("次の問題へ" if st.session_state.q_idx < len(problems)-1 else "採点して終了"):
        is_c = 1 if is_equal(ans, prob["answer"]) else 0
        res_df = pd.DataFrame([{
            "student_id": sid, "question": prob["question"],
            "student_answer": ans, "correct_answer": prob["answer"],
            "is_correct": is_c, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "type": q_type
        }])
        safe_save_results(res_df, get_result_file())
        
        if st.session_state.q_idx < len(problems) - 1:
            st.session_state.q_idx += 1
            st.rerun()
        else:
            st.session_state.done = True
            st.rerun()

# ==============================
# 4. 教師用画面
# ==============================

def teacher_view():
    subject = st.session_state.selected_subject
    st.header(f"🧑‍🏫 教師用管理（{subject}）")
    tab1, tab2, tab3 = st.tabs(["📊 成績分析", "📝 問題編集", "⚙️ データ管理"])

    with tab1:
        df = load_results()
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            # 簡易集計
            st.divider()
            st.subheader("👤 生徒別正答率")
            stats = df.groupby("student_id")["is_correct"].mean() * 100
            st.bar_chart(stats)
        else:
            st.info("解答データがありません。")

    with tab2:
        problems = load_problems()
        st.subheader("➕ 新規問題作成")
        
        q_type = st.selectbox("形式を選択", ["記述式", "選択式"])
        nq = st.text_area("問題文を入力")
        
        options = []
        if q_type == "選択式":
            st.write("選択肢を入力してください")
            o1 = st.text_input("選択肢A")
            o2 = st.text_input("選択肢B")
            o3 = st.text_input("選択肢C")
            o4 = st.text_input("選択肢D")
            options = [o1, o2, o3, o4]
            na = st.selectbox("正解となる選択肢", options)
        else:
            na = st.text_input("正解の文字列")

        if st.button("問題を登録"):
            if nq and na:
                new_p = {"type": q_type, "question": nq, "answer": na}
                if q_type == "選択式": new_p["options"] = options
                problems.append(new_p)
                save_problems(problems)
                st.success("登録完了")
                st.rerun()

        st.divider()
        st.subheader("登録済みの問題一覧")
        for i, p in enumerate(problems):
            with st.expander(f"問{i+1}: {p['question'][:20]}... ({p.get('type', '記述')})"):
                st.write(f"正解: {p['answer']}")
                if st.button("この問題を削除", key=f"dq_{i}"):
                    problems.pop(i)
                    save_problems(problems)
                    st.rerun()

    with tab3:
        st.subheader("📦 成績データの整理")
        
        if st.button("📁 現在の成績をアーカイブ（保存）する"):
            path = get_result_file()
            if os.path.exists(path):
                ts = datetime.now().strftime("%Y%m%d_%H%M")
                new_path = path.replace(".csv", f"_{ts}.csv")
                os.rename(path, new_path)
                st.success(f"アーカイブ完了: {new_path}")
                st.rerun()

        st.divider()
        st.subheader("📁 アーカイブ済みファイル（個別削除・DL）")
        
        # 過去ファイルをリストアップ
        archive_files = sorted(glob.glob(f"{subject}_results_*.csv"), reverse=True)
        
        if archive_files:
            selected_file = st.selectbox("操作するファイルを選択", archive_files)
            
            try:
                # プレビュー時も文字化け防止
                temp_df = pd.read_csv(selected_file, encoding='utf-8-sig')
                
                c1, c2 = st.columns(2)
                with c1:
                    # Excelで開けるようにDL
                    csv_data = temp_df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📥 Excel用CSVをダウンロード",
                        data=csv_data,
                        file_name=selected_file,
                        mime="text/csv"
                    )
                with c2:
                    # ★ご要望の個別削除機能
                    if st.button("🗑️ このファイルを完全に削除"):
                        os.remove(selected_file)
                        st.error(f"削除しました: {selected_file}")
                        time.sleep(0.5)
                        st.rerun()
                
                st.write("プレビュー:")
                st.dataframe(temp_df)
            except:
                st.warning("形式が古いか破損しています。下のボタンで削除してください。")
                if st.button("🗑️ この破損ファイルを削除"):
                    os.remove(selected_file)
                    st.rerun()
        else:
            st.info("過去のアーカイブはありません。")

# ==============================
# 5. メイン
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
    cols = st.columns(len(SUBJECTS))
    for i, sub in enumerate(SUBJECTS):
        with cols[i]:
            if st.button(sub, use_container_width=True):
                st.session_state.selected_subject = sub
                st.success(f"{sub} を選択中")

elif st.session_state.mode == "student":
    student_view()

elif st.session_state.mode == "auth":
    pw = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        if pw == TEACHER_PASSWORD:
            st.session_state.mode = "teacher"; st.rerun()
        else: st.error("不一致")

elif st.session_state.mode == "teacher":
    teacher_view()