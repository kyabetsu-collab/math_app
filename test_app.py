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
        # Excel対応形式で読み込み
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
# 3. 各画面
# ==============================

def student_view():
    subject = st.session_state.selected_subject
    st.header(f"✏️ {subject} テスト")
    sid = st.text_input("生徒IDを入力")
    if not sid: return

    problems = load_problems()
    if not problems:
        st.warning("問題がありません")
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
    st.subheader(f"問題 {st.session_state.q_idx + 1}")
    st.info(prob["question"])
    ans = st.text_input("答えを入力", key=f"q_{st.session_state.q_idx}")

    if st.button("次へ / 完了"):
        is_c = 1 if is_equal(ans, prob["answer"]) else 0
        res_df = pd.DataFrame([{
            "student_id": sid, "question": prob["question"],
            "student_answer": ans, "correct_answer": prob["answer"],
            "is_correct": is_c, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }])
        safe_save_results(res_df, get_result_file())
        
        if st.session_state.q_idx < len(problems) - 1:
            st.session_state.q_idx += 1
            st.rerun()
        else:
            st.session_state.done = True
            st.rerun()

def teacher_view():
    subject = st.session_state.selected_subject
    st.header(f"🧑‍🏫 管理画面（{subject}）")
    tab1, tab2, tab3 = st.tabs(["📊 成績", "📝 編集", "⚙️ ファイル管理"])

    with tab1:
        df = load_results()
        if not df.empty:
            st.dataframe(df)
        else:
            st.info("成績データがありません。")

    with tab2:
        # 問題追加・削除ロジック（既存）
        problems = load_problems()
        nq = st.text_area("新しい問題文")
        na = st.text_input("正解")
        if st.button("登録"):
            problems.append({"question": nq, "answer": na})
            save_problems(problems)
            st.rerun()

    with tab3:
        st.subheader("📦 成績データの整理")
        
        # 現在のファイルをアーカイブ
        if st.button("📁 現在の成績をアーカイブに送る"):
            path = get_result_file()
            if os.path.exists(path):
                new_path = path.replace(".csv", f"_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
                os.rename(path, new_path)
                st.success(f"アーカイブ完了: {new_path}")
                st.rerun()

        st.divider()
        st.subheader("📁 アーカイブ済みファイル（個別削除・DL）")
        
        # 過去ファイルをリストアップ
        archive_files = sorted(glob.glob(f"{subject}_results_*.csv"), reverse=True)
        
        if archive_files:
            selected_file = st.selectbox("操作する過去ログを選択", archive_files)
            
            try:
                # プレビュー時もutf-8-sigを明示
                temp_df = pd.read_csv(selected_file, encoding='utf-8-sig')
                
                col_dl, col_del = st.columns(2)
                with col_dl:
                    # ダウンロード
                    csv_data = temp_df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📥 Excel用CSVをダウンロード",
                        data=csv_data,
                        file_name=selected_file,
                        mime="text/csv"
                    )
                with col_del:
                    # 個別削除
                    if st.button("🗑️ このファイルを完全に消去"):
                        os.remove(selected_file)
                        st.error(f"ファイルを削除しました: {selected_file}")
                        time.sleep(0.5)
                        st.rerun()
                
                st.dataframe(temp_df)
            except:
                st.warning("形式が古いか破損しています。下のボタンで削除してください。")
                if st.button("🗑️ このファイルを消去する"):
                    os.remove(selected_file)
                    st.rerun()
        else:
            st.info("アーカイブはありません。")

# ==============================
# 4. メイン
# ==============================
st.set_page_config(page_title="総合学習分析アプリ", layout="wide")

if "mode" not in st.session_state: st.session_state.mode = None
if "selected_subject" not in st.session_state: st.session_state.selected_subject = "数学"

with st.sidebar:
    if st.button("🏠 ホーム"): st.session_state.mode = None; st.rerun()
    st.divider()
    if st.button("✏️ 生徒用テスト"): st.session_state.mode = "student"; st.rerun()
    if st.button("🧑‍🏫 教師用画面"): st.session_state.mode = "auth"; st.rerun()

if st.session_state.mode == "student":
    student_view()
elif st.session_state.mode == "auth":
    pw = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        if pw == TEACHER_PASSWORD:
            st.session_state.mode = "teacher"; st.rerun()
        else: st.error("違います")
elif st.session_state.mode == "teacher":
    teacher_view()
else:
    st.title("学習分析アプリ")
    st.session_state.selected_subject = st.selectbox("教科を選択してください", SUBJECTS)
    st.info("サイドバーから開始してください。")