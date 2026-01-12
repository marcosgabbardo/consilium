# Consilium

**Multi-Agent Investment Analysis CLI** — Harness the wisdom of legendary investors through AI-powered stock analysis.

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/anthropic-claude--opus--4.5-purple.svg" alt="Claude Opus 4.5">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/agents-20-orange.svg" alt="20 Agents">
</p>

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Investor Agents](#investor-agents)
   - [Analyze](#analyze)
   - [Compare](#compare)
   - [Ask Investor (Q&A)](#ask-investor-qa)
   - [Agent Management](#agent-management)
4. [Portfolio Management](#portfolio-management)
   - [Creating Portfolios](#creating-portfolios)
   - [Adding Positions](#adding-positions)
   - [Selling Positions](#selling-positions)
   - [Transaction History](#transaction-history)
   - [Portfolio Analysis](#portfolio-analysis)
   - [CSV Import](#csv-import)
5. [Watchlists](#watchlists)
   - [CRUD Operations](#watchlist-crud-operations)
   - [Watchlist Analysis](#watchlist-analysis)
6. [Stock Universes](#stock-universes)
   - [Available Universes](#available-universes)
   - [Universe Commands](#universe-commands)
7. [Backtesting](#backtesting)
   - [Running Backtests](#running-backtests)
   - [Backtest Strategies](#backtest-strategies)
   - [Backtest History](#backtest-history)
8. [History & Tracking](#history--tracking)
   - [Analysis History](#analysis-history)
   - [Q&A History](#qa-history)
9. [Cost Estimation](#cost-estimation)
10. [Database Management](#database-management)
11. [Configuration](#configuration)
12. [Architecture](#architecture)
13. [Troubleshooting](#troubleshooting)

---

## Overview

Consilium simulates a **hedge fund investment committee** where 20 specialized AI agents—each embodying the investment philosophy of legendary investors like Warren Buffett, Charlie Munger, Jim Simons, and Peter Lynch—analyze stocks and reach a weighted consensus.

The name comes from Latin *consilium* ("council" or "deliberation"), reflecting the collaborative decision-making process at the heart of the system.

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    consilium analyze AAPL                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              1. MARKET DATA (Yahoo Finance)                      │
│         Price, fundamentals, technicals (cached in MySQL)        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              2. SPECIALIST ANALYSIS (Parallel)                   │
│   Valuation │ Fundamentals │ Technicals │ Sentiment │ Risk      │
│                  Portfolio │ Political Risk                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              3. INVESTOR ANALYSIS (Parallel)                     │
│  Buffett │ Munger │ Graham │ Lynch │ Burry │ Simons │ ...       │
│         Each applies their unique investment philosophy          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 4. WEIGHTED CONSENSUS                            │
│      Final signal with confidence score (auto-saved to DB)       │
└─────────────────────────────────────────────────────────────────┘
```

### Key Features

- **13 Investor Personalities** — Each with distinct investment philosophies
- **7 Specialist Agents** — Quantitative analysis covering valuation, fundamentals, technicals, sentiment, risk, portfolio fit, and political risk
- **Ask Investor Q&A** — Direct questions to specific investors about stocks or strategies
- **Weighted Consensus Algorithm** — Agents vote with configurable weights and confidence levels
- **Portfolio Management** — Import positions, track BUY/SELL transactions, realized & unrealized P&L
- **Cost Estimation** — Shows estimated API costs before execution with user confirmation
- **Stock Universe Management** — Pre-built universes (S&P 500, NASDAQ 100, Dow 30, MAG7, Brazilian)
- **Watchlist Management** — Create, manage, and batch-analyze stock watchlists
- **Asset Comparison** — Side-by-side comparison with ranking and agent consensus matrix
- **Backtesting Engine** — Test strategies against historical data with Sharpe, Sortino, Calmar ratios
- **Analysis History** — All analyses automatically saved to MySQL with full tracking
- **International Markets** — Support for global exchanges (US, Brazil `.SA`, Europe, Asia)
- **Rich CLI Output** — Beautiful tables and panels with detailed reasoning
- **Export Formats** — JSON, CSV, and Markdown reports

---

## Installation

### Prerequisites

- Python 3.11+
- MySQL 8.0+
- Anthropic API key

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/consilium.git
cd consilium

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Environment Variables

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...

# Database (MySQL)
CONSILIUM_DB_HOST=localhost
CONSILIUM_DB_PORT=3306
CONSILIUM_DB_USER=consilium
CONSILIUM_DB_PASSWORD=your_password
CONSILIUM_DB_NAME=consilium
```

### Database Setup

```bash
# Create database
mysql -u root -p -e "CREATE DATABASE consilium;"
mysql -u root -p -e "CREATE USER 'consilium'@'localhost' IDENTIFIED BY 'your_password';"
mysql -u root -p -e "GRANT ALL PRIVILEGES ON consilium.* TO 'consilium'@'localhost';"

# Initialize schema (runs migrations)
consilium db init
```

---

## Investor Agents

### The Investment Committee

#### Investor Agents (13)

| Agent | Style | Philosophy |
|-------|-------|------------|
| **Warren Buffett** | Value | Wonderful companies at fair prices, economic moats, long-term compounding |
| **Charlie Munger** | Value | Mental models, multidisciplinary thinking, quality over price |
| **Ben Graham** | Value | Quantitative screens, margin of safety, net-net valuations |
| **Aswath Damodaran** | Value | DCF valuation, story-driven analysis, academic rigor |
| **Peter Lynch** | Growth | 10-baggers, invest in what you know, PEG ratio |
| **Phil Fisher** | Growth | Scuttlebutt method, qualitative analysis, long holding periods |
| **Cathie Wood** | Growth | Disruptive innovation, exponential technologies, 5-year horizons |
| **Michael Burry** | Contrarian | Deep value, balance sheet analysis, contrarian bets |
| **Bill Ackman** | Activist | Concentrated positions, operational improvements, catalysts |
| **Mohnish Pabrai** | Value | Dhandho framework, low-risk/high-uncertainty bets |
| **Rakesh Jhunjhunwala** | Momentum | Indian markets expertise, growth at reasonable price |
| **Stanley Druckenmiller** | Macro | Top-down analysis, asymmetric risk/reward, position sizing |
| **Jim Simons** | Quantitative | Mathematical models, statistical patterns, data-driven decisions |

#### Specialist Agents (7)

| Specialist | Focus |
|------------|-------|
| **Valuation Analyst** | DCF, comparables, intrinsic value estimation |
| **Fundamentals Analyst** | Financial statements, profitability, balance sheet strength |
| **Technical Analyst** | Price patterns, momentum indicators, support/resistance |
| **Sentiment Analyst** | Market sentiment, institutional positioning, contrarian signals |
| **Risk Manager** | Volatility, drawdown potential, systematic vs idiosyncratic risk |
| **Portfolio Manager** | Position sizing, entry strategy, portfolio fit |
| **Political Risk Analyst** | Electoral cycles, government intervention, geopolitical factors |

---

### Analyze

Run multi-agent analysis on one or more stocks.

```bash
# Analyze a single stock
consilium analyze AAPL

# Analyze multiple stocks
consilium analyze "AAPL,NVDA,MSFT"

# Verbose output with detailed reasoning
consilium analyze AAPL --verbose

# International markets
consilium analyze PETR3.SA    # Brazilian (B3)
consilium analyze 7203.T      # Tokyo
consilium analyze BMW.DE      # Frankfurt
```

#### Filter Agents

```bash
# Use only specific investors
consilium analyze TSLA --agents buffett,munger,burry

# Skip specialist analysis (faster)
consilium analyze AAPL --skip-specialists
consilium analyze AAPL -s
```

#### Export Results

```bash
# Export to JSON, CSV, or Markdown
consilium analyze AMZN --export json -o analysis.json
consilium analyze AMZN --export csv -o analysis.csv
consilium analyze AMZN --export md -o analysis.md
```

---

### Compare

Compare multiple assets side-by-side with ranked comparisons and agent consensus matrices.

```bash
# Basic comparison (ranked by score)
consilium compare AAPL,MSFT,GOOGL

# Sort by different metrics
consilium compare AAPL,MSFT,GOOGL --sort score      # Default: weighted score
consilium compare AAPL,MSFT,GOOGL --sort agreement  # Agent agreement ratio
consilium compare AAPL,MSFT,GOOGL --sort bullish    # Buy vote count

# Show agent consensus matrix (who voted what)
consilium compare NVDA,AMD,INTC --matrix

# Show themes/risks comparison
consilium compare TSLA,F,GM --themes

# Full verbose output (all views)
consilium compare AAPL,MSFT,GOOGL,NVDA --verbose

# Filter specific agents
consilium compare AAPL,MSFT --agents buffett,munger,simons --verbose
```

**Example Output:**

```
            Asset Comparison (sorted by score)
┏━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Rank ┃ Ticker ┃ Signal     ┃ Score  ┃ Confidence ┃ Agreement ┃ Votes          ┃
┡━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ 1    │ NVDA   │ STRONG_BUY │ 78.5   │ VERY_HIGH  │ 92%       │ 11B 1H 1S      │
│ 2    │ MSFT   │ BUY        │ 52.3   │ HIGH       │ 85%       │ 9B 3H 1S       │
│ 3    │ AAPL   │ HOLD       │ 12.1   │ MEDIUM     │ 62%       │ 5B 6H 2S       │
│ 4    │ GOOGL  │ HOLD       │ 8.7    │ MEDIUM     │ 58%       │ 4B 7H 2S       │
└──────┴────────┴────────────┴────────┴────────────┴───────────┴────────────────┘

Winner: NVDA with STRONG_BUY signal and 92% agreement
```

---

### Ask Investor (Q&A)

Ask direct questions to specific investor agents about stocks, strategies, or market views.

```bash
# Ask a single investor
consilium ask "O que você acha de TSLA?" --agent buffett
consilium ask "What's your view on NVDA for the next 2 years?" --agent lynch

# Ask multiple investors and compare responses
consilium ask "Vale investir em AAPL agora?" --agents buffett,munger,graham
consilium ask "Should I buy IBIT and short MSTR?" --agents buffett,simons

# With explicit ticker (forces market data fetch)
consilium ask "Is it overvalued?" --ticker GOOGL --agent damodaran

# Philosophical questions (no market data)
consilium ask "What do you think about investing in AI?" --agent buffett --no-data

# Skip cost confirmation
consilium ask "Quick take on META?" --agent wood --yes
```

**Example Output:**

```
╭──────────────────── Warren Buffett's Response ────────────────────╮
│                                                                    │
│ Question: "O que você acha de TSLA?"                               │
│ Tickers: TSLA (current: $248.50)                                   │
│                                                                    │
│ Signal: HOLD          Confidence: MEDIUM          Score: 0.0      │
│                                                                    │
│ ─────────────────────────────────────────────────────────────────  │
│                                                                    │
│ "Tesla represents a fascinating case study in modern investing.    │
│ The company has achieved remarkable things under Elon Musk's       │
│ leadership, building a dominant position in EVs and creating       │
│ substantial brand value..."                                        │
│                                                                    │
│ Key Factors:                                                       │
│ • EV market leadership provides competitive moat                   │
│ • Manufacturing efficiency is impressive                           │
│                                                                    │
│ Risks:                                                             │
│ • Intensifying competition from legacy automakers                  │
│ • Margin compression as EV market matures                          │
│                                                                    │
│ Time Horizon: 3-5 years                                            │
╰────────────────────────────────────────────────────────────────────╯

Cost: $0.08 | Tokens: 2,100 in / 650 out | Time: 3.2s
```

**Multiple Investors Comparison:**

```
                        Response Summary
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Investor            ┃ Signal   ┃ Confidence ┃ Score    ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━┩
│ Warren Buffett      │ BUY      │ HIGH       │ +42.5    │
│ Charlie Munger      │ BUY      │ HIGH       │ +42.5    │
│ Benjamin Graham     │ HOLD     │ MEDIUM     │ 0.0      │
└─────────────────────┴──────────┴────────────┴──────────┘

Consensus: BUY (2 bullish, 1 neutral, 0 bearish)
```

---

### Agent Management

```bash
# List all agents
consilium agents list

# Show agent weights
consilium agents list --weights

# Filter by type
consilium agents list --type investor
consilium agents list --type specialist

# Agent details
consilium agents info buffett
```

---

## Portfolio Management

Manage your investment portfolios with position tracking, P&L analysis, CSV import, and multi-agent analysis.

### Creating Portfolios

```bash
# Create a new portfolio
consilium portfolio create "Tech Holdings" -d "My tech investments"

# List all portfolios
consilium portfolio list

# Delete a portfolio
consilium portfolio delete "Tech Holdings"
consilium portfolio delete "Tech Holdings" --force  # Skip confirmation
```

### Adding Positions

```bash
# Add positions manually (BUY transactions)
consilium portfolio add "Tech Holdings" AAPL 100 150.00 --date 2024-01-15
consilium portfolio add "Tech Holdings" NVDA 50 450.00 --date 2024-02-01
consilium portfolio add "Tech Holdings" MSFT 30 380.00  # Uses today's date

# Show portfolio with live P&L
consilium portfolio show "Tech Holdings"
consilium portfolio show "Tech Holdings" --refresh  # Fetch latest prices
```

### Selling Positions

```bash
# Sell shares (records SELL transaction with P&L calculation)
consilium portfolio sell "Tech Holdings" AAPL 50 180.00
consilium portfolio sell "Tech Holdings" NVDA 25 520.00 --date 2024-06-15
consilium portfolio sell "Tech Holdings" MSFT 10 400.00 --fees 9.99 -n "Taking profits"
```

### Transaction History

```bash
# View transaction history (buys and sells)
consilium portfolio transactions "Tech Holdings"
consilium portfolio transactions "Tech Holdings" --ticker AAPL
consilium portfolio transactions "Tech Holdings" --type sell
consilium portfolio transactions "Tech Holdings" --limit 100

# View realized P&L summary (from closed positions)
consilium portfolio pnl "Tech Holdings"
consilium portfolio pnl "Tech Holdings" --ticker AAPL
```

**Transaction History Output:**

```
                           Transaction History
┏━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Date       ┃ Ticker ┃ Type ┃  Qty   ┃  Price  ┃    Total   ┃ Realized P&L ┃
┡━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ 2024-01-15 │ AAPL   │ BUY  │    100 │ $150.00 │ $15,000.00 │          -   │
│ 2024-03-01 │ AAPL   │ BUY  │     50 │ $160.00 │  $8,000.00 │          -   │
│ 2024-06-15 │ AAPL   │ SELL │     75 │ $180.00 │ $13,500.00 │   +$2,250.00 │
└────────────┴────────┴──────┴────────┴─────────┴────────────┴──────────────┘
```

### Portfolio Analysis

```bash
# Analyze portfolio with multi-agent system
consilium portfolio analyze "Tech Holdings"
consilium portfolio analyze "Tech Holdings" --verbose
consilium portfolio analyze "Tech Holdings" --agents buffett,munger,simons
consilium portfolio analyze "Tech Holdings" --skip-specialists --yes

# Export analysis results
consilium portfolio analyze "Tech Holdings" --export json -o analysis.json

# View analysis history
consilium portfolio analysis-history "Tech Holdings"
```

**Portfolio Summary Output:**

```
╭───────────────────────────── Portfolio Summary ──────────────────────────────╮
│ Tech Holdings                                                                │
│                                                                              │
│ Total Value: $51,156.96 USD                                                  │
│ Cost Basis: $31,350.00                                                       │
│                                                                              │
│ Unrealized P&L: +$19,806.96 (+63.18%)                                        │
│ Realized P&L: +$2,250.00                                                     │
│ Total P&L: +$22,056.96                                                       │
│                                                                              │
│ Positions: 4 | Transactions: 12                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### CSV Import

Import positions from brokerage CSV exports with automatic column detection.

```bash
# Import positions from CSV
consilium portfolio import "Tech Holdings" holdings.csv
consilium portfolio import "Tech Holdings" holdings.csv --preview  # Preview first

# Import with custom column mapping
consilium portfolio import "Tech Holdings" broker_export.csv \
    --ticker symbol --quantity shares --price avg_cost

# View import history
consilium portfolio import-history "Tech Holdings"
```

**Recognized CSV Headers:**

| Field | Recognized Headers |
|-------|-------------------|
| Ticker | ticker, symbol, stock, security, code, asset |
| Quantity | quantity, qty, shares, units, amount, position |
| Price | purchase_price, price, cost, avg_cost, buy_price |
| Date | purchase_date, date, buy_date, trade_date |
| Type | type, transaction_type, action, side, buy_sell |
| Fees | fees, fee, commission, brokerage, charges |
| Notes | notes, note, comment, description, memo |

**Transaction Type Values:**
- BUY: `buy`, `b`, `compra`, `long`, `+`, `bought`, `purchase`
- SELL: `sell`, `s`, `venda`, `short`, `-`, `sold`, `sale`

---

## Watchlists

Organize your stocks into watchlists for easier tracking and batch analysis.

### Watchlist CRUD Operations

```bash
# Create a new watchlist
consilium watchlist create tech-giants AAPL MSFT GOOGL NVDA META
consilium watchlist create value-picks BRK-B JNJ PG KO -d "Dividend aristocrats"

# List all watchlists
consilium watchlist list

# Show watchlist details
consilium watchlist show tech-giants

# Add tickers to existing watchlist
consilium watchlist add tech-giants AMZN TSLA

# Remove tickers from watchlist
consilium watchlist remove tech-giants META

# Delete a watchlist
consilium watchlist delete old-list
consilium watchlist delete old-list --force  # Skip confirmation
```

### Watchlist Analysis

```bash
# Analyze all tickers in a watchlist
consilium watchlist analyze tech-giants
consilium watchlist analyze tech-giants --verbose
consilium watchlist analyze tech-giants --agents buffett,munger
```

---

## Stock Universes

Access pre-built stock universes from major indices for batch analysis.

### Available Universes

| Universe | Description | Tickers |
|----------|-------------|---------|
| `sp500` | S&P 500 - Large Cap US equities | ~500 |
| `sp100` | S&P 100 - Top 100 US Blue Chips | ~100 |
| `nasdaq100` | NASDAQ 100 - Tech-heavy US stocks | ~100 |
| `dow30` | Dow Jones Industrial Average | 30 |
| `mag7` | Magnificent 7 - Tech megacaps | 7 |
| `brazilian` | Top Brazilian stocks (B3) | 20 |
| `dax` | DAX - German Blue Chips | 40 |
| `ftse100` | FTSE 100 - UK largest companies | 100 |
| `nikkei225` | NIKKEI 225 - Japanese Blue Chips | 225 |
| `eurostoxx50` | Euro Stoxx 50 - Eurozone Blue Chips | 50 |

### Universe Commands

```bash
# List all available universes (with population status)
consilium universe list

# Populate a universe from external data source
consilium universe populate sp500
consilium universe populate mag7
consilium universe populate --all  # Populate all universes

# Show universe details and tickers
consilium universe show mag7
consilium universe show dow30

# Re-sync universe data (fetch latest constituents)
consilium universe sync sp500

# Analyze all tickers in a universe
consilium universe analyze mag7
consilium universe analyze mag7 --verbose
consilium universe analyze dow30 --agents buffett,simons

# For large universes, use --limit to sample random tickers
consilium universe analyze sp500 --limit 20 --agents buffett,munger

# Delete a universe from database
consilium universe delete old-universe
consilium universe delete old-universe --force
```

---

## Backtesting

Test agent recommendations against historical data with comprehensive risk metrics.

### Running Backtests

```bash
# Basic backtest (uses simulated signals if no historical data)
consilium backtest AAPL --period 2y

# With specific date range
consilium backtest AAPL --start 2023-01-01 --end 2025-01-01

# Custom benchmark (default: SPY)
consilium backtest NVDA --benchmark QQQ --period 2y

# Filter specific agents
consilium backtest TSLA --agents buffett,simons,lynch --period 1y

# Custom capital and slippage
consilium backtest MSFT --capital 50000 --slippage 0.15 --period 2y

# Verbose output with full trade history
consilium backtest AAPL --period 2y --verbose
```

### Backtest Strategies

**Signal-Based Strategy** (default):
- BUY on `BUY` or `STRONG_BUY` signals
- SELL on `SELL` or `STRONG_SELL` signals
- HOLD on `HOLD` signals

```bash
consilium backtest AAPL --strategy signal --period 2y
```

**Threshold-Based Strategy**:
- BUY when score exceeds threshold
- SELL when score falls below negative threshold

```bash
consilium backtest AAPL --strategy threshold --threshold 50 --period 2y
```

### Backtest Metrics

| Category | Metrics |
|----------|---------|
| **Returns** | Total Return, CAGR, Alpha, Excess Return |
| **Risk** | Sharpe Ratio, Sortino Ratio, Calmar Ratio, Max Drawdown, VaR (95%), Beta |
| **Trade Stats** | Total Trades, Win Rate, Profit Factor, Avg Holding Period |

**Example Output:**

```
╭────────────────────────────── Backtest Results ──────────────────────────────╮
│ Ticker: AAPL                                                                 │
│ Period: 2024-01-12 to 2026-01-12 (731 days)                                  │
│ Strategy: Signal                                                             │
│ Benchmark: SPY                                                               │
│ Initial Capital: $100,000.00                                                 │
│                                                                              │
│ Final Value: $115,939.49                                                     │
│ Total Return: +15.94% ($+15,939.49)                                          │
│ Alpha vs SPY: -0.85%                                                         │
╰──────────────────────────────────────────────────────────────────────────────╯
             Returns

   CAGR                  +7.72%
   Benchmark Return     +49.31%
   Excess Return        -33.37%

           Risk Metrics

   Sharpe Ratio            0.28
   Sortino Ratio           0.39
   Calmar Ratio            0.37
   Max Drawdown         -21.09%
   VaR (95%)             -2.05%
   Beta                    0.34

           Trade Statistics

   Total Trades                   10
   Win Rate                    60.0%
   Profit Factor                2.34
   Avg Holding Period        77 days
```

### Backtest History

```bash
# List all backtests
consilium backtest-history

# Filter by ticker
consilium backtest-history --ticker AAPL --limit 20

# View details of a specific backtest (with full trade log)
consilium backtest-show 1
```

---

## History & Tracking

### Analysis History

All analyses are automatically saved to the database for future reference.

```bash
# List recent analyses
consilium history list

# Filter by ticker
consilium history list --ticker AAPL --limit 20

# Filter by date and signal
consilium history list --days 7 --signal BUY

# Show details of a specific analysis
consilium history show abc123
consilium history show abc123 --verbose

# Export history to file
consilium history export -o history.csv --days 30
consilium history export -o history.json -f json --ticker AAPL
```

### Q&A History

Q&A sessions with investors are also saved for reference.

```bash
# View Q&A history
consilium ask history
consilium ask history --agent buffett --limit 10

# Show details of a specific question
consilium ask show 1
```

---

## Cost Estimation

Before any API call, Consilium shows an estimated cost breakdown and asks for confirmation.

```bash
# Standard analysis (shows cost, asks for confirmation)
consilium analyze AAPL

# Skip confirmation (for scripts/automation)
consilium analyze AAPL --yes
consilium compare AAPL,MSFT,GOOGL --yes
consilium watchlist analyze tech-giants --yes
consilium universe analyze mag7 --yes
consilium ask "What about NVDA?" --agent buffett --yes
```

**Example Output:**

```
╭────────────────────────────── Cost Estimation ───────────────────────────────╮
│ Model: Claude Opus 4.5                                                       │
│ Model ID: claude-opus-4-5-20251101                                           │
│                                                                              │
│  Component    Calls  Input Tokens  Output Tokens   Cost                      │
│  Specialists      7        ~4,200         ~3,500  $0.33                      │
│  Investors       13       ~32,500         ~9,100  $1.17                      │
│  Total           20       ~36,700        ~12,600  $1.50                      │
│                                                                              │
│ Estimated Cost: $1.50 USD                                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
Proceed with analysis? [y/N]:
```

**Estimated Costs (Claude Opus 4.5):**

| Scenario | API Calls | Cost |
|----------|-----------|------|
| 1 ticker (full pipeline) | 20 | ~$1.50 |
| 1 ticker (no specialists) | 13 | ~$0.94 |
| 3 tickers (compare) | 60 | ~$4.50 |
| MAG7 universe | 140 | ~$10.50 |
| Q&A (1 agent) | 1 | ~$0.08 |
| Q&A (3 agents) | 3 | ~$0.25 |

---

## Database Management

```bash
# Check configuration status
consilium status

# Database status
consilium db status

# Initialize/update database schema
consilium db init

# Show version
consilium --version
```

### Database Tables

| Table | Purpose |
|-------|---------|
| `analysis_history` | All analysis results with consensus |
| `agent_responses` | Individual agent recommendations |
| `specialist_reports` | Specialist analysis reports |
| `market_data_cache` | Cached Yahoo Finance data |
| `watchlists` | User-defined stock lists |
| `stock_universes` | Pre-built index universes |
| `price_history` | Historical price data |
| `portfolios` | User investment portfolios |
| `portfolio_positions` | Individual positions in portfolios |
| `portfolio_transactions` | BUY/SELL transaction history |
| `portfolio_imports` | CSV import history |
| `portfolio_analysis` | Portfolio-level analysis results |
| `ask_questions` | Q&A session history |
| `ask_responses` | Individual agent Q&A responses |
| `backtest_runs` | Backtest execution results |
| `backtest_trades` | Individual trades in backtests |
| `backtest_snapshots` | Daily portfolio snapshots |
| `schema_versions` | Migration tracking |

---

## Configuration

### Agent Weights

Customize how much each agent's opinion matters in the final consensus:

```bash
# In .env file
CONSILIUM_WEIGHT_BUFFETT=2.0      # Legendary track record
CONSILIUM_WEIGHT_MUNGER=1.8       # Partner to Buffett
CONSILIUM_WEIGHT_SIMONS=1.8       # Quantitative legend
CONSILIUM_WEIGHT_GRAHAM=1.5       # Father of value investing
CONSILIUM_WEIGHT_DRUCKENMILLER=1.5 # Macro master
CONSILIUM_WEIGHT_WOOD=1.0         # Growth/innovation focus
```

### Cache TTLs

Control how long market data is cached (in minutes):

```bash
CONSILIUM_CACHE_PRICE_TTL=5           # 5 minutes
CONSILIUM_CACHE_FUNDAMENTALS_TTL=1440 # 24 hours
CONSILIUM_CACHE_TECHNICALS_TTL=60     # 1 hour
CONSILIUM_CACHE_INFO_TTL=10080        # 1 week
```

### Consensus Thresholds

Adjust the score thresholds for final signals:

```bash
CONSILIUM_THRESHOLD_STRONG_BUY=60
CONSILIUM_THRESHOLD_BUY=20
CONSILIUM_THRESHOLD_SELL=-20
CONSILIUM_THRESHOLD_STRONG_SELL=-60
```

### Consensus Algorithm

The weighted consensus algorithm combines individual agent signals:

| Signal | Score |
|--------|-------|
| STRONG_BUY | +100 |
| BUY | +50 |
| HOLD | 0 |
| SELL | -50 |
| STRONG_SELL | -100 |

| Confidence | Multiplier |
|------------|------------|
| VERY_HIGH | 1.0 |
| HIGH | 0.85 |
| MEDIUM | 0.7 |
| LOW | 0.5 |
| VERY_LOW | 0.3 |

```
weighted_score = Σ(signal_score × agent_weight × confidence_mult) / Σ(weight × conf)
```

---

## Architecture

```
consilium/
├── cli.py                 # Typer CLI application
├── config.py              # Pydantic Settings configuration
├── core/
│   ├── models.py          # Stock, AgentResponse, ConsensusResult
│   ├── portfolio_models.py # Portfolio, Position, Analysis models
│   ├── enums.py           # SignalType, ConfidenceLevel, etc.
│   └── exceptions.py      # Custom exception hierarchy
├── data/
│   ├── yahoo.py           # Yahoo Finance data provider
│   ├── cache.py           # Cache-aside pattern with MySQL
│   └── universes.py       # Stock universe data provider
├── db/
│   ├── connection.py      # Async MySQL connection pool
│   ├── migrations.py      # Schema DDL (versioned migrations)
│   ├── repository.py      # Analysis/Watchlist data access
│   ├── portfolio_repository.py  # Portfolio data access layer
│   └── ask_repository.py  # Q&A history persistence
├── agents/
│   ├── base.py            # BaseAgent, InvestorAgent, SpecialistAgent
│   └── registry.py        # Agent factory and discovery
├── prompts/
│   ├── investors/         # 13 investor personality YAMLs
│   └── specialists/       # 7 specialist analysis YAMLs
├── llm/
│   ├── client.py          # Async Anthropic client with retry
│   ├── cost_estimator.py  # API cost estimation
│   ├── prompts.py         # Prompt builder with templates
│   └── ask_prompts.py     # Q&A-specific prompts
├── analysis/
│   ├── orchestrator.py    # Multi-agent pipeline coordination
│   └── consensus.py       # Weighted voting algorithm
├── ask/
│   ├── orchestrator.py    # Q&A orchestration
│   ├── models.py          # AskResponse, AskResult
│   └── ticker_extractor.py # Extract tickers from questions
├── portfolio/
│   ├── importer.py        # CSV import with auto-detection
│   └── analyzer.py        # Portfolio analysis orchestration
├── backtesting/
│   ├── engine.py          # Backtest orchestrator
│   ├── strategies.py      # Signal & threshold strategies
│   ├── simulator.py       # Trade execution simulator
│   ├── metrics.py         # Financial metrics calculator
│   ├── models.py          # BacktestResult, BacktestTrade, etc.
│   └── repository.py      # Backtest persistence
└── output/
    ├── formatters.py      # Rich tables and panels
    ├── comparison.py      # Asset comparison formatter
    ├── ask_formatter.py   # Q&A output formatter
    ├── portfolio_formatter.py  # Portfolio display formatter
    ├── backtest_formatter.py  # Backtest results formatter
    └── exporters.py       # JSON, CSV, MD export
```

### Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| CLI Framework | Typer + Rich |
| LLM | Anthropic Claude Opus 4.5 |
| Market Data | Yahoo Finance |
| Data Validation | Pydantic v2 |
| Database | MySQL 8.0 (aiomysql) |
| Async Runtime | asyncio |
| YAML Config | PyYAML |

---

## Troubleshooting

### API Errors

```bash
# If you see "credit balance is too low" error
# You need to add credits to your Anthropic account
# Visit: https://console.anthropic.com/settings/billing
```

### Database Issues

```bash
# Reset database (WARNING: deletes all data)
consilium db init --reset

# Check connection
consilium db status
```

### International Tickers

```bash
# Brazilian stocks need .SA suffix
consilium analyze PETR3.SA   # Correct
consilium analyze PETR3      # Wrong - will get 404

# Common exchange suffixes:
# .SA  - Brazil (B3)
# .L   - London
# .DE  - Germany (Xetra)
# .T   - Tokyo
# .HK  - Hong Kong
```

---

## Roadmap

- [x] Historical analysis tracking
- [x] Political risk analysis
- [x] Jim Simons quantitative agent
- [x] International market support
- [x] Watchlist management (CRUD + batch analysis)
- [x] Stock universes (S&P 500, NASDAQ 100, Dow 30, MAG7, etc.)
- [x] Cost estimation with user confirmation
- [x] Asset comparison (side-by-side analysis)
- [x] Portfolio management (import, P&L tracking, analysis)
- [x] Transaction tracking (BUY/SELL with realized P&L)
- [x] Ask Investor Q&A (direct questions to agents)
- [x] Backtesting engine (signal & threshold strategies, full metrics suite)
- [ ] Advanced screening with presets
- [ ] Agent debates (bull vs bear)
- [ ] Web dashboard interface
- [ ] Slack/Discord integration for alerts

---

## Disclaimer

**This software is for educational and research purposes only.**

Consilium does not provide financial advice. The AI-generated analysis should not be construed as investment recommendations. Always conduct your own research and consult with qualified financial advisors before making investment decisions.

Past performance of the investors whose philosophies are simulated does not guarantee future results. The simulated agents are interpretations and do not represent the actual views or recommendations of the real individuals.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

<p align="center">
  <i>Built with Claude Opus 4.5 and a passion for quantitative investing.</i>
</p>
