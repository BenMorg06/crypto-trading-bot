import websockets, json, asyncio
import pandas as pd
from ta.trend import EMAIndicator
from binance.client import Client
from openpyxl.workbook import Workbook
from dotenv import load_dotenv
import os

# Load the .env file
load_dotenv()


pd.options.mode.chained_assignment = None

# Binance API credentials
api_key = os.getenv('API_KEY')
api_secret = os.getenv('API_SECRET')

client = Client(api_key, api_secret, testnet=True)

stream = websockets.connect(
    "wss://stream.binance.com:9443/stream?streams=btcusdt@miniTicker"
)

df = pd.DataFrame()
open_position = False
o_data = {
    'EntryTimeStamp':[],
    'Invested':[], 
    'CloseTimeStamp':[],
    'Profit/Loss(£)':[],
    'Profit/Loss(%)':[]
    }
order_data = pd.DataFrame(o_data)
print(order_data)


def createframe(msg):
    df = pd.DataFrame([msg])
    df = df.loc[:, ["s", "E", "c"]]
    df.columns = ["Symbol", "Time", "Price"]
    df.Price = df.Price.astype(float)
    df.Time = pd.to_datetime(df.Time, unit="ms")
    return df

async def main():
    global df, open_position, order_data
    async with stream as receiver:
        while True:
            data = await receiver.recv()
            data = json.loads(data)["data"]
            df = pd.concat([df, createframe(data)], ignore_index=True)

            # Calculate the EMA
            if len(df) > 60:  # Make sure there are enough data points
                ema_indicator = EMAIndicator(close=df['Price'], window=60)
                print(ema_indicator)
                df['EMA_12'] = ema_indicator.ema_indicator()
                if not open_position:
                # Example: Buy condition when the price crosses above the EMA
                    if df['Price'].iloc[-1] > df['EMA_12'].iloc[-1]:
                        order = client.order_market_buy(symbol='BTCUSDT', 
                                                        quantity=0.01)
                        print(order)
                        open_position = True
                        buyprice = float(order['fills'][0]['price'])
                        print(buyprice)
                        new_row = {'EntryTimeStamp':df['Time'].iloc[-1],
                                   'Invested':buyprice*0.01
                                   }
                if open_position:
                    # Example: Sell condition when the price crosses below the EMA
                    subdf = df[df.Time >= pd.to_datetime(order['transactTime'], unit='ms')]
                    if len(subdf)>1:
                        if subdf.iloc[-1].Price < buyprice*0.9995 or \
                        df.iloc[-1].Price  > buyprice*1.0002:
                            order = client.order_market_sell(symbol='BTCUSDT', 
                                                            quantity=0.01)
                            print(order)
                            sellprice = float(order['fills'][0]['price'])
                            print(f"you made {(sellprice-buyprice)/buyprice} profit")
                            open_position = False
                            new_row['CloseTimeStamp'] = df['Time'].iloc[-1]
                            new_row['Profit/Loss(£)'] = (sellprice-buyprice)*0.01
                            new_row['Profit/Loss(%)'] = (((sellprice-buyprice)*0.01)/buyprice)*100
                            order_data.loc[len(order_data)] = new_row
                

            print(df.iloc[-1])
            print(order_data)
            order_data.to_excel("order_data.xlsx", index=False)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

