import os
import csv
import requests
import yfinance as yf
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = os.getenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")

CANDIDATE_FILE = "logs/daily_candidates.csv"

MIN_SCORE = 80
MAX_ORDERS_PER_DAY = 1
ORDER_DOLLARS = 100
TAKE_PROFIT_PCT = 0.04
STOP_LOSS_PCT = 0.02


def alpaca_headers():
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Content-Type": "application/json",
    }


def check_alpaca_config():
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("Alpaca API 키가 없습니다. .env를 확인하세요.")
        return False
    return True


def get_account():
    url = f"{ALPACA_BASE_URL}/v2/account"

    try:
        response = requests.get(url, headers=alpaca_headers(), timeout=30)

        if response.status_code != 200:
            print(f"계좌 조회 실패: {response.status_code} / {response.text}")
            return None

        return response.json()

    except Exception as e:
        print(f"계좌 조회 오류: {e}")
        return None


def load_today_strong_candidates():
    today = datetime.now().strftime("%Y-%m-%d")
    candidates = []
    seen_tickers = set()

    if not os.path.isfile(CANDIDATE_FILE):
        print("daily_candidates.csv 파일이 없습니다. 먼저 main.py를 실행하세요.")
        return candidates

    with open(CANDIDATE_FILE, mode="r", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    rows.sort(
        key=lambda row: int(float(row.get("score", 0))),
        reverse=True
    )

    for row in rows:
        try:
            score = int(float(row["score"]))
        except Exception:
            continue

        ticker = row.get("ticker", "").strip().upper()

        if row.get("date") != today:
            continue

        if score < MIN_SCORE:
            continue

        if ticker in seen_tickers:
            continue

        seen_tickers.add(ticker)

        candidates.append({
            "date": row["date"],
            "ticker": ticker,
            "sector": row.get("sector", ""),
            "change": row.get("change", ""),
            "volume_ratio": row.get("volume_ratio", ""),
            "market_cap": row.get("market_cap", ""),
            "score": score,
            "label": row.get("label", ""),
        })

    return candidates


def has_open_position(symbol):
    url = f"{ALPACA_BASE_URL}/v2/positions/{symbol}"

    try:
        response = requests.get(url, headers=alpaca_headers(), timeout=30)

        if response.status_code == 200:
            return True

        if response.status_code == 404:
            return False

        print(f"{symbol} 포지션 조회 실패: {response.status_code} / {response.text}")
        return True

    except Exception as e:
        print(f"{symbol} 포지션 조회 오류: {e}")
        return True


def has_open_order(symbol):
    url = f"{ALPACA_BASE_URL}/v2/orders"

    params = {
        "status": "open",
        "symbols": symbol,
        "limit": 50,
    }

    try:
        response = requests.get(url, headers=alpaca_headers(), params=params, timeout=30)

        if response.status_code != 200:
            print(f"{symbol} 주문 조회 실패: {response.status_code} / {response.text}")
            return True

        orders = response.json()
        return len(orders) > 0

    except Exception as e:
        print(f"{symbol} 주문 조회 오류: {e}")
        return True


def get_latest_price(symbol):
    try:
        data = yf.Ticker(symbol).history(period="5d")

        if data.empty:
            return None

        return float(data["Close"].iloc[-1])

    except Exception as e:
        print(f"{symbol} 현재가 조회 오류: {e}")
        return None


def place_market_order(symbol):
    price = get_latest_price(symbol)

    if price is None:
        print(f"{symbol}: 현재가 조회 실패로 주문 스킵")
        return None

    take_profit = round(price * (1 + TAKE_PROFIT_PCT), 2)
    stop_loss = round(price * (1 - STOP_LOSS_PCT), 2)

    url = f"{ALPACA_BASE_URL}/v2/orders"

    payload = {
        "symbol": symbol,
        "notional": str(ORDER_DOLLARS),
        "side": "buy",
        "type": "market",
        "time_in_force": "day",
        "order_class": "bracket",
        "take_profit": {
            "limit_price": take_profit
        },
        "stop_loss": {
            "stop_price": stop_loss
        }
    }

    try:
        response = requests.post(url, headers=alpaca_headers(), json=payload, timeout=30)

        if response.status_code in [200, 201]:
            print(f"브래킷 Paper 주문 성공: {symbol} / ${ORDER_DOLLARS}")
            print(f"기준가: {price:.2f} / 익절: {take_profit} / 손절: {stop_loss}")
            return response.json()

        print(f"Paper 주문 실패: {symbol} / {response.status_code} / {response.text}")
        return None

    except Exception as e:
        print(f"Paper 주문 오류: {symbol} / {e}")
        return None


def run_auto_trader():
    print("\n[ALPACA PAPER AUTO TRADER]")
    print("Mode: PAPER ONLY")
    print("Date:", datetime.now().strftime("%Y-%m-%d"))

    if not check_alpaca_config():
        return

    account = get_account()
    if not account:
        return

    print(f"Account Status: {account.get('status')}")
    print(f"Buying Power: {account.get('buying_power')}")

    candidates = load_today_strong_candidates()

    if not candidates:
        print("오늘 자동매매 대상 강력 후보가 없습니다.")
        return

    print("\nStrong Candidates:")
    for c in candidates:
        print(f"{c['ticker']} | Score {c['score']} | {c['label']}")

    order_count = 0

    for candidate in candidates:
        symbol = candidate["ticker"]

        if order_count >= MAX_ORDERS_PER_DAY:
            print("일일 최대 주문 수 도달. 추가 주문 중단.")
            break

        if has_open_position(symbol):
            print(f"{symbol}: 이미 보유 중이라 주문 스킵")
            continue

        if has_open_order(symbol):
            print(f"{symbol}: 미체결 주문 존재로 스킵")
            continue

        result = place_market_order(symbol)

        if result:
            order_count += 1

    print(f"\n자동매매 완료: 신규 주문 {order_count}건")


if __name__ == "__main__":
    run_auto_trader()