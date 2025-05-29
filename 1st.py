import discord
from discord.ext import commands
import ccxt

TOKEN = "11212121212121211212"
INITIAL_BALANCE = 10000
FEE_RATE = 0.0005
MAX_LEVERAGE = 125
PREFIX = "!"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

exchange = ccxt.binance()
users = {}

def get_price(symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        return ticker['last']
    except:
        return None

def calculate_pnl(entry_price, exit_price, amount, side):
    if side == "long":
        gross = (exit_price - entry_price) * amount
    else:
        gross = (entry_price - exit_price) * amount
    fee = (entry_price + exit_price) * amount * FEE_RATE
    return gross - fee

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.command()
async def balance(ctx):
    uid = str(ctx.author.id)
    user = users.setdefault(uid, {"balance": INITIAL_BALANCE, "positions": [], "pnl": 0})
    await ctx.send(f"💰 {ctx.author.name} 잔고: {user['balance']:.2f} USDT")

@bot.command()
async def buy(ctx, symbol: str, usdt: float, leverage: int):
    await enter_position(ctx, symbol, usdt, leverage, "long")

@bot.command()
async def sell(ctx, symbol: str, usdt: float, leverage: int):
    await enter_position(ctx, symbol, usdt, leverage, "short")

async def enter_position(ctx, symbol, usdt, leverage, side):
    uid = str(ctx.author.id)
    user = users.setdefault(uid, {"balance": INITIAL_BALANCE, "positions": [], "pnl": 0})

    if leverage < 1 or leverage > MAX_LEVERAGE:
        await ctx.send(f"❌ 레버리지는 1~{MAX_LEVERAGE}배로 입력해주세요.")
        return

    symbol = symbol.upper()
    price = get_price(symbol)
    if price is None:
        await ctx.send(f"❌ `{symbol}` 는 마켓에 없습니다.")
        return

    amount = (usdt * leverage) / price
    fee = usdt * FEE_RATE
    total_cost = usdt + fee

    if user["balance"] < total_cost:
        await ctx.send("❌ 잔고 부족")
        return

    user["balance"] -= total_cost
    user["positions"].append({
        "symbol": symbol,
        "entry": price,
        "amount": amount,
        "leverage": leverage,
        "used_margin": usdt,
        "side": side
    })

    emoji = "✅" if side == "long" else "📉"
    direction = "롱" if side == "long" else "숏"
    await ctx.send(f"{emoji} {symbol} {direction} 진입: {usdt} USDT x{leverage}배 @ {price:.2f}")

@bot.command(name="close")
async def close_position(ctx, symbol: str):
    uid = str(ctx.author.id)
    user = users.get(uid)

    if not user or not user["positions"]:
        await ctx.send("❌ 보유 포지션 없음")
        return

    for i, pos in enumerate(user["positions"]):
        if pos["symbol"] == symbol.upper():
            current_price = get_price(symbol.upper())
            if current_price is None:
                await ctx.send(f"❌ `{symbol}` 현재 가격을 가져올 수 없습니다.")
                return

            pnl = calculate_pnl(pos["entry"], current_price, pos["amount"], pos["side"])
            user["balance"] += pos["used_margin"] + pnl
            user["pnl"] += pnl
            del user["positions"][i]

            await ctx.send(
                f"💸 {symbol.upper()} {pos['side'].upper()} 포지션 종료 @ {current_price:.2f}, PnL: {pnl:.2f} USDT"
            )
            return

    await ctx.send(f"❌ `{symbol}` 포지션을 찾을 수 없습니다.")

@bot.command()
async def position(ctx):
    uid = str(ctx.author.id)
    user = users.get(uid)

    if not user or not user["positions"]:
        await ctx.send("📭 현재 보유 중인 포지션이 없습니다.")
        return

    msg = f"📊 {ctx.author.name}님의 현재 포지션:\n"
    for pos in user["positions"]:
        current_price = get_price(pos["symbol"])
        if current_price:
            pnl = calculate_pnl(pos["entry"], current_price, pos["amount"], pos["side"])
            msg += (
                f"- {pos['symbol']} | {pos['side'].upper()} @ {pos['entry']:.2f} → {current_price:.2f} | "
                f"PnL: {pnl:.2f} USDT\n"
            )
        else:
            msg += f"- {pos['symbol']} | 가격 정보 불러오기 실패\n"

    await ctx.send(msg)

@bot.command()
async def rank(ctx):
    if not users:
        await ctx.send("📉 아직 거래 내역이 없습니다.")
        return

    leaderboard = sorted(users.items(), key=lambda x: x[1]["pnl"], reverse=True)
    msg = "**🏆 수익 랭킹 (PnL 기준)**\n"
    for i, (uid, data) in enumerate(leaderboard[:10], 1):
        user = await bot.fetch_user(int(uid))
        pnl_pct = (data["pnl"] / INITIAL_BALANCE) * 100
        msg += f"{i}. {user.name}: {data['pnl']:.2f} USDT ({pnl_pct:.2f}%)\n"
    await ctx.send(msg)

bot.run(TOKEN)
