import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

CSV_FILE = "logs/daily_candidates.csv"
PARAM_FILE = "logs/strategy_params.csv"


def load_data():
    try:
        df = pd.read_csv(CSV_FILE)
        return df
    except:
        print("데이터 없음")
        return None


def add_returns(df):
    returns_1d = []
    returns_3d = []

    for _, row in df.iterrows():
        ticker = row["ticker"]
        date = row["date"]

        try:
            start = datetime.strptime(date, "%Y-%m-%d")
            end = start + timedelta(days=5)

            data = yf.download(ticker, start=start, end=end)

            if len(data) < 2:
                returns_1d.append(None)
                returns_3d.append(None)
                continue

            r1 = (data["Close"].iloc[1] - data["Close"].iloc[0]) / data["Close"].iloc[0] * 100
            returns_1d.append(round(r1, 2))

            if len(data) >= 4:
                r3 = (data["Close"].iloc[3] - data["Close"].iloc[0]) / data["Close"].iloc[0] * 100
                returns_3d.append(round(r3, 2))
            else:
                returns_3d.append(None)

        except:
            returns_1d.append(None)
            returns_3d.append(None)

    df["return_1d"] = returns_1d
    df["return_3d"] = returns_3d

    return df


def optimize_params(df):
    df = df.dropna(subset=["return_1d"])

    if len(df) < 5:
        print("데이터 부족 → 최적화 스킵")
        return None

    avg_return = df["return_1d"].mean()

    # 기본값
    tp = 0.04
    sl = 0.02

    # 간단한 자동 조정 로직
    if avg_return > 1.5:
        tp = 0.05
        sl = 0.02
    elif avg_return < 0:
        tp = 0.03
        sl = 0.015

    return tp, sl, round(avg_return, 2)


def save_params(tp, sl, avg_return):
    df = pd.DataFrame([{
        "date": datetime.now().strftime("%Y-%m-%d"),
        "take_profit": tp,
        "stop_loss": sl,
        "avg_return": avg_return
    }])

    df.to_csv(PARAM_FILE, index=False)
    print(f"최적화 저장 완료 → TP:{tp} SL:{sl} AVG:{avg_return}")


def main():
    print("\n[PERFORMANCE OPTIMIZER]")

    df = load_data()
    if df is None:
        return

    df = add_returns(df)

    result = optimize_params(df)

    if result:
        tp, sl, avg = result
        save_params(tp, sl, avg)


if __name__ == "__main__":
    main()