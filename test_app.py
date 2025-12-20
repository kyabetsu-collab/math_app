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
# 2. データ管理ロジック (強化版)
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
    """CSVからデータを読み込む（反映されない問題を回避するため、読み込み時に型を固定）"""
    path = get_result_file()
    if not os.path.exists(path):
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        df = pd.read_csv(path, encoding='utf-8-sig', engine='python')
        if df.empty:
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
        
        # 数値を確実に変換
        if "is_correct" in df.columns:
            df["is_correct"] = pd.to_numeric(df["is_correct"], errors='coerce').fillna(0).astype(int)
        return df
    except Exception:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def safe_save_results(new_df, path):
    """追記モードで保存"""
    try:
        header = not os.path.exists(path)
        new_df.to_csv(path, mode='a', index=False, header=header, encoding='utf-8-sig')
        return True
    except Exception as e:
        st.error(f"保存エラー: {e}")
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
        if sp.simplify(f"({s_expr}) - ({c_expr})") == 0: return True
    except: pass
    return False

# ==============================
# 3. 生徒用画面
# ==============================

def student_view():
    subject = st.session_state.selected_subject
    st.header(f"✏️ {subject} テスト")
    
    if "q_idx" not in st.session_state:
        st.session_state.q_idx = 0
        st.session_state.current_results = []
        st.session_state.done = False

    if "student_id" not in st.session_state or not st.session_state.student_id:
        sid = st.text_input("生徒ID（氏名など）を入力してください")
        if st.button("開始"):
            if sid:
                st.session_state.student_id = sid
                st.rerun()
            else: st.warning("IDを入力してください")
        return

    problems = load_problems()
    if not problems:
        st.warning("問題がありません。")
        return

    if st.session_state.done:
        st.balloons()
        st.success("提出完了！")
        score = sum([r["is_correct"] for r in st.session_state.current_results])
        total = len(st.session_state.current_results)
        st.metric("今回の結果", f"{score} / {total} 正解")
        
        if st.button("戻る"):
            for k in ["q_idx", "current_results", "done", "student_id"]:
                if k in st.session_state: del st.session_state[k]
            st.session_state.mode = None
            st.rerun()
        return

    prob = problems[st.session_state.q_idx]
    st.subheader(f"問題 {st.session_state.q_idx + 1} / {len(problems)}")
    st.info(prob["question"])
    
    q_type = prob.get("type", "記述式")
    if q_type == "選択式":
        ans = st.radio("答え", prob.get("options", []), key=f"q_{st.session_state.q_idx}")
    else:
        ans = st.text_input("答えを入力", key=f"q_{st.session_state.q_idx}")

    if st.button("次へ / 終了"):
        is_c = 1 if is_equal(ans, prob["answer"]) else 0
        res_entry = {
            "student_id": st.session_state.student_id, 
            "question": prob["question"],
            "student_answer": ans, 
            "correct_answer": prob["answer"],
            "is_correct": is_c, 
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "type": q_type
        }
        st.session_state.current_results.append(res_entry)
        safe_save_results(pd.DataFrame([res_entry]), get_result_file())
        
        if st.session_state.q_idx < len(problems) - 1:
            st.session_state.q_idx += 1
            st.rerun()
        else:
            st.session_state.done = True
            st.rerun()

# ==============================
# 4. 教師用画面 (分析機能強化)
# ==============================

def teacher_view():
    subject = st.session_state.selected_subject
    st.header(f"🧑‍🏫 分析・管理（{subject}）")
    tab1, tab2, tab3 = st.tabs(["📊 成績分析", "📝 問題編集", "⚙️ データ管理"])

    with tab1:
        df = load_results()
        if not df.empty:
            # --- 全体統計 ---
            st.subheader("📋 全体の概要")
            col1, col2, col3 = st.columns(3)
            col1.metric("受験者数", f"{df['student_id'].nunique()} 人")
            col2.metric("平均正答率", f"{(df['is_correct'].mean()*100):.1f} %")
            col3.metric("総解答数", f"{len(df)} 件")

            # --- 問題別正答率グラフ ---
            st.divider()
            st.subheader("❓ 問題ごとの正答率 (どの問題が難しいか)")
            # 問題文が長い場合に備え、短くカットして集計
            df['q_short'] = df['question'].str[:20] + "..."
            q_stats = df.groupby("q_short")["is_correct"].mean() * 100
            st.bar_chart(q_stats)
            st.caption("※グラフが低いほど、クラス全体が間違えやすい「難問」です。")

            # --- 個人別分析 ---
            st.divider()
            st.subheader("👤 生徒個別の詳細分析")
            selected_id = st.selectbox("詳細を表示する生徒を選択", sorted(df["student_id"].unique()))
            
            if selected_id:
                p_df = df[df["student_id"] == selected_id]
                p_score = p_df["is_correct"].mean() * 100
                st.write(f"### {selected_id} さんの結果 (正答率: {p_score:.1f}%)")
                
                # 正誤をアイコン化して表示
                display_df = p_df[["question", "student_answer", "correct_answer", "is_correct"]].copy()
                display_df["判定"] = display_df["is_correct"].map({1: "✅正解", 0: "❌不正解"})
                st.dataframe(display_df[["question", "student_answer", "correct_answer", "判定"]], use_container_width=True, hide_index=True)

            # --- ランキング表 ---
            st.divider()
            st.subheader("🥇 生徒別正答率一覧")
            ranking = df.groupby("student_id")["is_correct"].mean() * 100
            st.table(ranking.sort_values(ascending=False).rename("正答率(%)"))
        else:
            st.info(f"{subject} の解答データはまだありません。")

    with tab2:
        problems = load_problems()
        # 問題追加UI (省略せず記述)
        st.subheader("➕ 問題の追加")
        qt = st.selectbox("形式", ["記述式", "選択式"])
        qq = st.text_area("問題文")
        opts = []
        if qt == "選択式":
            o1 = st.text_input("選択肢A"); o2 = st.text_input("選択肢B")
            opts = [o1, o2]
            qa = st.selectbox("正解", opts)
        else: qa = st.text_input("正解の答え")

        if st.button("登録"):
            problems.append({"type": qt, "question": qq, "answer": qa, "options": opts})
            save_problems(problems)
            st.success("登録完了"); st.rerun()

    with tab3:
        if st.button("📁 データをリセット（アーカイブ）"):
            path = get_result_file()
            if os.path.exists(path):
                os.rename(path, path.replace(".csv", f"_{datetime.now().strftime('%Y%m%d%H%M')}.csv"))
                st.rerun()

# ==============================
# 5. メイン制御
# ==============================
st.set_page_config(page_title="学習分析システム", layout="wide")
if "mode" not in st.session_state: st.session_state.mode = None
if "selected_subject" not in st.session_state: st.session_state.selected_subject = "数学"

with st.sidebar:
    st.title("🍀 Menu")
    if st.button("🏠 教科選択へ"):
        for k in ["q_idx", "current_results", "done", "student_id", "mode"]:
            if k in st.session_state: del st.session_state[k]
        st.session_state.mode = None
        st.rerun()
    st.divider()
    st.write(f"教科: **{st.session_state.selected_subject}**")
    if st.button("✏️ テストを受ける"): st.session_state.mode = "student"; st.rerun()
    if st.button("🧑‍🏫 教師用画面"): st.session_state.mode = "auth"; st.rerun()

if st.session_state.mode is None:
    st.title("📚 教科を選択")
    cols = st.columns(len(SUBJECTS))
    for i, sub in enumerate(SUBJECTS):
        if cols[i].button(sub, use_container_width=True):
            st.session_state.selected_subject = sub
            st.rerun()
elif st.session_state.mode == "student": student_view()
elif st.session_state.mode == "auth":
    pw = st.text_input("Password", type="password")
    if st.button("Login"):
        if pw == TEACHER_PASSWORD: st.session_state.mode = "teacher"; st.rerun()
elif st.session_state.mode == "teacher": teacher_view()