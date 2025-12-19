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
# 1. 設定・定数
# ==============================
PROBLEM_FILE = "problems.json"
RESULT_FILE = "results.csv"
TEACHER_PASSWORD = "admin"  # 必要に応じて変更してください

REQUIRED_COLUMNS = [
    "student_id", "question", "student_answer", 
    "correct_answer", "is_correct", "timestamp"
]

# ==============================
# 2. データ管理・ユーティリティ
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
        if "is_correct" in df.columns:
            df["is_correct"] = pd.to_numeric(df["is_correct"], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

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
        if "," in s_expr or "," in c_expr:
            s_set = {sp.simplify(x) for x in s_expr.split(",")}
            c_set = {sp.simplify(x) for x in c_expr.split(",")}
            return s_set == c_set
        diff = sp.simplify(f"({s_expr}) - ({c_expr})")
        if diff == 0: return True
    except: pass
    return False

# ==============================
# 3. 生徒用画面 (課題1修正: 前に戻る機能)
# ==============================

def student_view():
    st.header("✏️ 生徒用テスト")
    sid = st.text_input("生徒ID（出席番号など）を入力", key="sid_input")
    if not sid:
        st.info("IDを入力して開始してください")
        return

    problems = load_problems()
    if not problems:
        st.warning("問題が登録されていません。")
        return

    # 初期化
    if "q_idx" not in st.session_state:
        st.session_state.q_idx = 0
        st.session_state.order = list(range(len(problems)))
        random.shuffle(st.session_state.order)
        st.session_state.answers_dict = {}  # 入力値を保持
        st.session_state.done = False

    if st.session_state.done:
        st.success("全ての解答を送信しました！")
        if st.button("新しくテストを受ける"):
            for key in ["q_idx", "order", "answers_dict", "done"]:
                if key in st.session_state: del st.session_state[key]
            st.rerun()
        return

    # 現在の問題
    idx = st.session_state.order[st.session_state.q_idx]
    prob = problems[idx]

    st.subheader(f"問題 {st.session_state.q_idx + 1} / {len(problems)}")
    st.info(prob["question"])
    
    # 保持されている答えがあれば復元
    saved_val = st.session_state.answers_dict.get(idx, "")
    ans = st.text_input("答えを入力", value=saved_val, key=f"q_field_{st.session_state.q_idx}")

    col1, col2 = st.columns(2)
    
    # 前へボタン
    with col1:
        if st.session_state.q_idx > 0:
            if st.button("← 前へ戻る"):
                st.session_state.answers_dict[idx] = ans  # 入力内容を一時保存
                st.session_state.q_idx -= 1
                st.rerun()

    # 次へ/終了ボタン
    with col2:
        is_last = (st.session_state.q_idx == len(problems) - 1)
        btn_label = "採点して終了 ➔" if is_last else "次へ進む ➔"
        
        if st.button(btn_label):
            # 解答を保存
            st.session_state.answers_dict[idx] = ans
            
            if is_last:
                # 全解答をまとめてCSVに書き出し
                results_to_save = []
                for p_idx, p_data in enumerate(problems):
                    # 全ての問題に対して解答（空欄含む）を取得
                    s_ans = st.session_state.answers_dict.get(p_idx, "")
                    is_correct = 1 if is_equal(s_ans, p_data["answer"]) else 0
                    results_to_save.append({
                        "student_id": sid, "question": p_data["question"],
                        "student_answer": s_ans, "correct_answer": p_data["answer"],
                        "is_correct": is_correct, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                
                res_df = pd.DataFrame(results_to_save)
                res_df.to_csv(RESULT_FILE, mode="a", header=not os.path.exists(RESULT_FILE), index=False)
                st.session_state.done = True
                st.rerun()
            else:
                st.session_state.q_idx += 1
                st.rerun()

# ==============================
# 4. 教師用画面 (課題2修正: 認証の安定化)
# ==============================

def teacher_view():
    st.header("🧑‍🏫 教師用管理パネル")
    tab1, tab2, tab3 = st.tabs(["📊 成績分析", "📝 問題編集", "⚙️ 設定"])

    df = load_results()

    with tab1:
        if df.empty:
            st.info("解答データがまだありません。生徒がテストを完了するとここに表示されます。")
        else:
            acc = df["is_correct"].mean() * 100
            c1, c2, c3 = st.columns(3)
            c1.metric("全体平均正答率", f"{acc:.1f}%")
            c2.metric("総解答データ数", len(df))
            c3.metric("受験ユニーク人数", df["student_id"].nunique())

            st.subheader("成績の分布")
            s_stats = df.groupby("student_id")["is_correct"].mean() * 100
            fig_hist = px.histogram(s_stats, x="is_correct", nbins=10, labels={'is_correct':'正答率(%)', 'count':'人数'})
            st.plotly_chart(fig_hist, use_container_width=True)

            st.subheader("問題別正答率（正答率が低い順）")
            q_stats = df.groupby("question")["is_correct"].mean().sort_values() * 100
            fig_bar = px.bar(x=q_stats.values, y=q_stats.index, orientation='h', color=q_stats.values, color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_bar, use_container_width=True)

    with tab2:
        problems = load_problems()
        with st.expander("➕ 新しい問題を追加"):
            nq = st.text_area("問題文を入力してください")
            na = st.text_input("正解を入力してください")
            if st.button("問題を登録"):
                if nq and na:
                    problems.append({"question": nq, "answer": na})
                    save_problems(problems)
                    st.success("登録しました")
                    st.rerun()
        
        for i, p in enumerate(problems):
            with st.expander(f"問{i+1}: {p['question'][:30]}..."):
                new_q = st.text_area("問題", p["question"], key=f"edit_q_{i}")
                new_a = st.text_input("正解", p["answer"], key=f"edit_a_{i}")
                col_save, col_del = st.columns(2)
                if col_save.button("更新", key=f"save_{i}"):
                    problems[i] = {"question": new_q, "answer": new_a}
                    save_problems(problems)
                    st.success("更新しました")
                if col_del.button("削除", key=f"del_{i}"):
                    problems.pop(i)
                    save_problems(problems)
                    st.rerun()

    with tab3:
        if st.button("🗑️ 全ての成績データをリセット"):
            if os.path.exists(RESULT_FILE): os.remove(RESULT_FILE)
            st.warning("データを全て削除しました。")
            st.rerun()

# ==============================
# 5. メインルーティング
# ==============================

st.set_page_config(page_title="数学学習分析アプリ", layout="wide")

if "mode" not in st.session_state:
    st.session_state.mode = None

# サイドバーメニュー
with st.sidebar:
    st.title("🍀 メニュー")
    if st.button("🏠 ホーム"):
        st.session_state.mode = None
        st.rerun()
    st.divider()
    if st.button("✏️ 生徒用テスト"):
        st.session_state.mode = "student"
        st.rerun()
    if st.button("🧑‍🏫 教師用画面"):
        # 教師モードに入っていない場合は認証へ
        if st.session_state.mode != "teacher":
            st.session_state.mode = "auth"
        st.rerun()

# 画面表示
if st.session_state.mode == "student":
    student_view()

elif st.session_state.mode == "auth":
    st.title("🧑‍🏫 教師用ログイン")
    pw_input = st.text_input("パスワードを入力", type="password")
    if st.button("ログイン"):
        if pw_input == TEACHER_PASSWORD:
            st.session_state.mode = "teacher"
            st.rerun()
        else:
            st.error("パスワードが違います")

elif st.session_state.mode == "teacher":
    teacher_view()

else:
    st.title("数学学習分析アプリ")
    st.write("このアプリは、簡単な反復練習、自動採点、そして詳細な成績分析をサポートします。")
    st.markdown("""
    ### 特徴
    - **生徒**: その場で採点結果を確認でき、前の問題に戻って修正も可能です。
    - **教師**: クラス全体の正答率分布や、どの問題が難しいかをリアルタイムで把握できます。
    """)
    st.info("左側のサイドバーからモードを選択してください。")