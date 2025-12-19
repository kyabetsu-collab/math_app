import streamlit as st
import json
import random
import pandas as pd
import numpy as np
import sympy as sp
import os
import unicodedata
import plotly.express as px
from datetime import datetime

# ==============================
# 設定・定数
# ==============================
PROBLEM_FILE = "problems.json"
RESULT_FILE = "results.csv"
TEACHER_PASSWORD = "admin"  # 必要に応じて変更

REQUIRED_COLUMNS = [
    "student_id", "question", "student_answer", 
    "correct_answer", "is_correct", "timestamp"
]

# ==============================
# データ管理
# ==============================

def load_problems():
    if not os.path.exists(PROBLEM_FILE): return []
    try:
        with open(PROBLEM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_problems(problems):
    with open(PROBLEM_FILE, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)

def load_results():
    if not os.path.exists(RESULT_FILE):
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        df = pd.read_csv(RESULT_FILE)
        # 【重要】計算エラーを防ぐために数値を強制変換
        if "is_correct" in df.columns:
            df["is_correct"] = pd.to_numeric(df["is_correct"], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

# ==============================
# 採点ロジック（数学的等価性の判定）
# ==============================

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
        # 数値比較
        if abs(float(s_raw) - float(c_raw)) < 1e-7: return True
    except: pass
    try:
        # 数式比較 (SymPy)
        s_expr = s_raw.replace("x=", "").replace("y=", "")
        c_expr = c_raw.replace("x=", "").replace("y=", "")
        if "," in s_expr or "," in c_expr:
            s_set = {sp.simplify(x) for x in s_expr.split(",")}
            c_set = {sp.simplify(x) for x in c_expr.split(",")}
            return s_set == c_set
        diff = sp.simplify(f"({s_expr}) - ({c_expr})")
        if diff == 0: return True
    except: pass
    return False

# ==============================
# 各画面の構築
# ==============================

def student_view():
    st.header("✏️ 生徒用テスト")
    sid = st.text_input("生徒ID（出席番号など）を入力")
    if not sid:
        st.info("IDを入力して開始してください")
        return

    problems = load_problems()
    if not problems:
        st.warning("問題が登録されていません。")
        return

    if "q_idx" not in st.session_state:
        st.session_state.q_idx = 0
        st.session_state.order = list(range(len(problems)))
        random.shuffle(st.session_state.order)
        st.session_state.answers = {}
        st.session_state.done = False

    if st.session_state.done:
        st.success("テスト完了！")
        if st.button("最初から解き直す"):
            del st.session_state.q_idx
            st.rerun()
        return

    idx = st.session_state.order[st.session_state.q_idx]
    prob = problems[idx]

    st.subheader(f"問題 {st.session_state.q_idx + 1} / {len(problems)}")
    st.markdown(f"#### {prob['question']}")
    
    ans = st.text_input("答えを入力", key=f"q_{idx}")
    
    col1, col2 = st.columns(2)
    if col2.button("次へ ➔"):
        # 採点と保存
        is_correct = 1 if is_equal(ans, prob["answer"]) else 0
        st.session_state.answers[idx] = {
            "student_id": sid, "question": prob["question"],
            "student_answer": ans, "correct_answer": prob["answer"],
            "is_correct": is_correct, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        if st.session_state.q_idx < len(problems) - 1:
            st.session_state.q_idx += 1
            st.rerun()
        else:
            # CSV保存
            res_df = pd.DataFrame(st.session_state.answers.values())
            res_df.to_csv(RESULT_FILE, mode="a", header=not os.path.exists(RESULT_FILE), index=False)
            st.session_state.done = True
            st.rerun()

def teacher_view():
    st.header("🧑‍🏫 教師用分析パネル")
    tab1, tab2, tab3 = st.tabs(["📊 成績分析", "📝 問題編集", "⚙️ 設定"])

    df = load_results()

    with tab1:
        if df.empty:
            st.info("まだ解答データがありません。")
        else:
            # 全体統計
            acc = df["is_correct"].mean() * 100
            c1, c2, c3 = st.columns(3)
            c1.metric("クラス平均正答率", f"{acc:.1f}%")
            c2.metric("総解答数", len(df))
            c3.metric("受験人数", df["student_id"].nunique())

            # 分布グラフ
            st.subheader("生徒別 正答率の分布")
            s_stats = df.groupby("student_id")["is_correct"].mean() * 100
            fig_hist = px.histogram(s_stats, x="is_correct", nbins=10, 
                                   labels={'is_correct':'正答率(%)', 'count':'人数'},
                                   title="何％取れた生徒が何人いるか")
            st.plotly_chart(fig_hist, use_container_width=True)

            # 問題別正答率
            st.subheader("問題ごとの正答率（低い順 = 難問）")
            q_stats = df.groupby("question")["is_correct"].mean().sort_values() * 100
            fig_bar = px.bar(x=q_stats.values, y=q_stats.index, orientation='h',
                            labels={'x':'正答率(%)', 'y':''}, color=q_stats.values,
                            color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_bar, use_container_width=True)

    with tab2:
        problems = load_problems()
        with st.expander("➕ 新問追加"):
            nq = st.text_area("問題文")
            na = st.text_input("正解")
            if st.button("追加"):
                problems.append({"question": nq, "answer": na})
                save_problems(problems)
                st.rerun()
        
        for i, p in enumerate(problems):
            with st.expander(f"問{i+1}: {p['question'][:20]}..."):
                problems[i]["question"] = st.text_area("問題", p["question"], key=f"q_{i}")
                problems[i]["answer"] = st.text_input("正解", p["answer"], key=f"a_{i}")
                if st.button("保存", key=f"s_{i}"):
                    save_problems(problems)
                    st.success("保存完了")
                if st.button("削除", key=f"d_{i}"):
                    problems.pop(i)
                    save_problems(problems)
                    st.rerun()

    with tab3:
        if st.button("全成績データをリセット"):
            if os.path.exists(RESULT_FILE): os.remove(RESULT_FILE)
            st.rerun()

# ==============================
# メイン実行
# ==============================
st.set_page_config(page_title="学習分析アプリ", layout="wide")

if "mode" not in st.session_state: st.session_state.mode = None

with st.sidebar:
    st.title("Menu")
    if st.button("🏠 ホーム"): st.session_state.mode = None
    if st.button("✏️ 生徒用テスト"): st.session_state.mode = "student"
    if st.button("🧑‍🏫 教師用画面"): st.session_state.mode = "auth"

if st.session_state.mode == "student":
    student_view()
elif st.session_state.mode == "auth":
    pw = st.text_input("パスワード", type="password")
    if pw == TEACHER_PASSWORD:
        st.session_state.mode = "teacher"
        st.rerun()
elif st.session_state.mode == "teacher":
    teacher_view()
else:
    st.title("学習分析アプリ")
    st.write("反復練習とリアルタイム分析で、効率的な学習をサポートします。")