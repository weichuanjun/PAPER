import yfinance as yf
import pandas as pd
import yaml
from pywebio.output import *
from pywebio.session import *
from pywebio.platform.tornado_http import start_server
from pywebio.input import *
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json
import os
import pyperclip

# 读取配置文件
with open('nikkei225.yaml', 'r', encoding='utf-8') as file:
    nikkei_225_config = yaml.safe_load(file)

RESULTS_FILE = 'static/scan_results.json'

# 创建static文件夹
if not os.path.exists('static'):
    os.makedirs('static')

# 检查股票
# def has_potential_signal(ticker):
#     try:
#         stock = yf.Ticker(ticker)
#         hist = stock.history(period="1mo", interval="1h")

#         if hist.empty:
#             return False

#         hist['RSI'] = RSIIndicator(close=hist['Close']).rsi()
#         hist['EMA'] = EMAIndicator(close=hist['Close'], window=14).ema_indicator()

#         latest_data = hist.iloc[-1]
#         return latest_data['RSI'] > 50 and latest_data['EMA'] > hist.iloc[-2]['EMA']
#     except Exception as e:
#         return False

def has_potential_signal(ticker):
    try:
        # 获取数据
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo", interval="1h")

        if hist.empty:
            return False

        # 计算RSI
        hist['RSI'] = RSIIndicator(close=hist['Close']).rsi()
        
        # 计算14周期EMA
        hist['EMA'] = EMAIndicator(close=hist['Close'], window=14).ema_indicator()

        # 计算MACD
        macd = MACD(close=hist['Close'])
        hist['MACD'] = macd.macd()
        hist['MACD_Signal'] = macd.macd_signal()

        # 获取最新的数据和前一个周期的数据
        latest_data = hist.iloc[-1]
        prev_data = hist.iloc[-2]

        # 信号判定逻辑
        rsi_signal = latest_data['RSI'] > 50
        ema_signal = latest_data['EMA'] > prev_data['EMA']
        macd_signal = latest_data['MACD'] > latest_data['MACD_Signal']

        # 综合判断是否存在潜在信号
        return rsi_signal and ema_signal and macd_signal
    except Exception as e:
        print(f"Error: {e}")
        return False

# 生成技术分析图
def generate_technical_charts(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo", interval="1h")

        hist['RSI'] = RSIIndicator(close=hist['Close']).rsi()
        hist['EMA'] = EMAIndicator(close=hist['Close'], window=14).ema_indicator()
        hist['MACD'] = MACD(close=hist['Close']).macd()
        hist['Signal'] = MACD(close=hist['Close']).macd_signal()

        fig, axs = plt.subplots(4, 1, figsize=(10, 20))

        # Plot closing price and EMA
        axs[0].plot(hist.index, hist['Close'], label='Close')
        axs[0].plot(hist.index, hist['EMA'], label='EMA', linestyle='--')
        axs[0].legend()
        axs[0].set_title('Close Price and EMA')

        # Plot RSI
        axs[1].plot(hist.index, hist['RSI'], label='RSI')
        axs[1].axhline(30, linestyle='--', color='red')
        axs[1].axhline(70, linestyle='--', color='green')
        axs[1].set_title('RSI')
        axs[1].legend()

        # Plot MACD and Signal
        axs[2].plot(hist.index, hist['MACD'], label='MACD')
        axs[2].plot(hist.index, hist['Signal'], label='Signal', linestyle='--')
        axs[2].set_title('MACD')
        axs[2].legend()

        # Plot Volume
        axs[3].bar(hist.index, hist['Volume'], label='Volume')
        axs[3].set_title('Volume')
        axs[3].legend()

        plt.tight_layout()
        plt.savefig(f'static/{ticker}.png')
        plt.close()
    except Exception as e:
        pass

# 生成公司财报和基本信息
def generate_financial_report(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        financials = stock.financials.T
        balance_sheet = stock.balance_sheet.T
        cash_flow = stock.cashflow.T

        financials.index = financials.index.year
        balance_sheet.index = balance_sheet.index.year
        cash_flow.index = cash_flow.index.year

        financials_html = financials.T.to_html()
        balance_sheet_html = balance_sheet.T.to_html()
        cash_flow_html = cash_flow.T.to_html()

        return info, financials_html, balance_sheet_html, cash_flow_html, financials, balance_sheet, cash_flow
    except Exception as e:
        return {}, '', '', '', pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def update_display(potential_stocks):
    try:
        with use_scope('result_scope', clear=True):
            if potential_stocks:
                tabs = []
                for stock_info in potential_stocks:
                    info, financials_html, balance_sheet_html, cash_flow_html, financials, balance_sheet, cash_flow = generate_financial_report(stock_info['code'])
                    sector = stock_info.get('sector', 'N/A')
                    tab_content = [
                        put_button("Copy", onclick=lambda fi=financials, bs=balance_sheet, cf=cash_flow, inf=info: copy_to_clipboard(inf, fi, bs, cf)),
                        put_text(f"銘柄コード: {stock_info['code']}"),
                        put_text(f"会社名: {stock_info['name']}"),
                        put_text(f"セクター: {sector}"),
                        put_html('<hr>'),
                        put_image(open(f'static/{stock_info["code"]}.png', 'rb').read(), width='100%'),
                        put_html('<h3>基本情報</h3>'),
                        put_text(f"市場価格: {info.get('regularMarketPrice', 'N/A')}"),
                        put_text(f"時価総額: {info.get('marketCap', 'N/A')}"),
                        put_text(f"PER: {info.get('trailingPE', 'N/A')}"),
                        put_text(f"ROE: {info.get('returnOnEquity', 'N/A')}"),
                        put_text(f"PBR: {info.get('priceToBook', 'N/A')}"),
                        put_text(f"配当利回り: {info.get('dividendYield', 'N/A')}"),
                        put_html('<h3>財務諸表</h3>'),
                        put_html('<h4>損益計算書</h4>'),
                        put_scrollable(put_html(financials_html), height=200),
                        put_html('<h4>貸借対照表</h4>'),
                        put_scrollable(put_html(balance_sheet_html), height=200),
                        put_html('<h4>キャッシュフロー計算書</h4>'),
                        put_scrollable(put_html(cash_flow_html), height=200),
                    ]
                    tabs.append({'title': stock_info['name'], 'content': tab_content})

                put_tabs(tabs)
            else:
                put_text("本日は上昇信号を示す銘柄はありません。")
    except Exception as e:
        pass

def copy_to_clipboard(info, financials, balance_sheet, cash_flow):
    try:
        data = f"市場価格: {info.get('regularMarketPrice', 'N/A')}\n"
        data += f"時価総額: {info.get('marketCap', 'N/A')}\n"
        data += f"PER: {info.get('trailingPE', 'N/A')}\n"
        data += f"ROE: {info.get('returnOnEquity', 'N/A')}\n"
        data += f"PBR: {info.get('priceToBook', 'N/A')}\n"
        data += f"配当利回り: {info.get('dividendYield', 'N/A')}\n\n"

        data += "損益計算書:\n"
        data += financials.to_string() + "\n\n"
        data += "貸借対照表:\n"
        data += balance_sheet.to_string() + "\n\n"
        data += "キャッシュフロー計算書:\n"
        data += cash_flow.to_string()

        pyperclip.copy(data)
        toast("情報がクリップボードにコピーされました。")
    except Exception as e:
        pass

def search_stock(ticker):
    try:
        ticker = ticker + ".T"
        potential_stocks = [{'code': ticker, 'name': ticker, 'sector': 'N/A'}]
        generate_technical_charts(ticker)
        update_display(potential_stocks)
    except Exception as e:
        pass

def scan_stocks():
    potential_stocks = []
    try:
        for stock_info in nikkei_225_config['stocks']:
            ticker = stock_info['code']

            if has_potential_signal(ticker):
                potential_stocks.append(stock_info)
                generate_technical_charts(stock_info['code'])

        save_results(potential_stocks)
    except Exception as e:
        pass
    return potential_stocks

def save_results(results):
    try:
        with open(RESULTS_FILE, 'w') as file:
            json.dump(results, file)
    except Exception as e:
        pass

def load_results():
    try:
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE, 'r') as file:
                return json.load(file)
    except Exception as e:
        pass
    return []

def main():
    # put_text("日経225銘柄のスキャンを開始します。")

    previous_results = load_results()

    # 初始化搜索框
    with use_scope('search_scope', clear=True):
        input_group("检索", [
            actions('', [
                {'label': 'Find', 'value': 'find'}
            ], name='action')
        ], validate=handle_action)

    # 初始化日志框
    put_scrollable(put_scope('log_output', content=''), height=200, keep_bottom=True)
    
    # 初始化结果显示框
    put_scope('result_scope')

    # 显示之前的结果
    if previous_results:
        update_display(previous_results)

def handle_action(data):
    action = data['action']
    if action == 'search':
        search_stock(data['ticker'])
    elif action == 'find':
        start_find()

def start_find():
    potential_stocks = scan_stocks()
    update_display(potential_stocks)

if __name__ == '__main__':
    start_server(main, port=8040)
