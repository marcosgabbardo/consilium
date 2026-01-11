# Consilium

**Multi-Agent Investment Analysis CLI** — Harness the wisdom of legendary investors through AI-powered stock analysis.

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/anthropic-claude--opus--4.5-purple.svg" alt="Claude Opus 4.5">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/agents-20-orange.svg" alt="20 Agents">
</p>

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

---

## Features

- **13 Investor Personalities** — Each with distinct investment philosophies, from value investing to growth, momentum, macro, and **quantitative** strategies
- **7 Specialist Agents** — Quantitative analysis covering valuation, fundamentals, technicals, sentiment, risk, portfolio fit, and **political risk**
- **Weighted Consensus Algorithm** — Agents vote with configurable weights and confidence levels
- **Stock Universe Management** — Pre-built universes (S&P 500, NASDAQ 100, Dow 30, MAG7, Brazilian) for batch analysis
- **Watchlist Management** — Create, manage, and batch-analyze stock watchlists
- **Analysis History** — All analyses automatically saved to MySQL with full tracking
- **International Markets** — Support for global exchanges (US, Brazil `.SA`, Europe, Asia)
- **Parallel Execution** — Async architecture for fast multi-agent analysis
- **Rich CLI Output** — Beautiful tables and panels with detailed reasoning
- **Export Formats** — JSON, CSV, and Markdown reports
- **MySQL Caching** — Smart caching of market data with configurable TTLs

---

## The Investment Committee

### Investor Agents (13)

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

### Specialist Agents (7)

| Specialist | Focus |
|------------|-------|
| **Valuation Analyst** | DCF, comparables, intrinsic value estimation |
| **Fundamentals Analyst** | Financial statements, profitability, balance sheet strength |
| **Technical Analyst** | Price patterns, momentum indicators, support/resistance |
| **Sentiment Analyst** | Market sentiment, institutional positioning, contrarian signals |
| **Risk Manager** | Volatility, drawdown potential, systematic vs idiosyncratic risk |
| **Portfolio Manager** | Position sizing, entry strategy, portfolio fit |
| **Political Risk Analyst** | Electoral cycles, government intervention, geopolitical factors, regulatory risk |

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

# Optional: Customize agent weights (0-10 scale)
CONSILIUM_WEIGHT_BUFFETT=2.0
CONSILIUM_WEIGHT_MUNGER=1.8
CONSILIUM_WEIGHT_SIMONS=1.8
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

## Usage

### Basic Analysis

```bash
# Analyze a single stock
consilium analyze AAPL

# Analyze multiple stocks
consilium analyze "AAPL,NVDA,MSFT"

# Verbose output with detailed reasoning
consilium analyze AAPL --verbose
```

### International Markets

```bash
# Brazilian stocks (B3 exchange)
consilium analyze PETR3.SA    # Petrobras
consilium analyze VALE3.SA    # Vale
consilium analyze ITUB4.SA    # Itaú

# Other markets
consilium analyze 7203.T      # Toyota (Tokyo)
consilium analyze BMW.DE      # BMW (Frankfurt)
consilium analyze 0700.HK     # Tencent (Hong Kong)
```

### Filter Agents

```bash
# Use only specific investors
consilium analyze TSLA --agents buffett,munger,burry

# Include the quantitative analyst
consilium analyze NVDA --agents simons,burry,druckenmiller

# Skip specialist analysis (faster)
consilium analyze AAPL --skip-specialists
# Or use the short flag
consilium analyze AAPL -s
```

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

### Export Results

```bash
# Export to JSON
consilium analyze AMZN --export json -o analysis.json

# Export to CSV
consilium analyze AMZN --export csv -o analysis.csv

# Export to Markdown
consilium analyze AMZN --export md -o analysis.md
```

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

### Watchlist Management

Organize your stocks into watchlists for easier tracking and batch analysis.

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

# Analyze all tickers in a watchlist
consilium watchlist analyze tech-giants
consilium watchlist analyze tech-giants --verbose
consilium watchlist analyze tech-giants --agents buffett,munger

# Delete a watchlist
consilium watchlist delete old-list
consilium watchlist delete old-list --force  # Skip confirmation
```

**Example Output:**

```
                               Watchlists
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Name         ┃ Description           ┃ Created    ┃ Updated    ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ tech-giants  │ -                     │ 2026-01-11 │ 2026-01-11 │
│ value-picks  │ Dividend aristocrats  │ 2026-01-11 │ 2026-01-11 │
└──────────────┴───────────────────────┴────────────┴────────────┘

╭─────────────────────── Watchlist: tech-giants ────────────────────────╮
│ Description: Big tech companies                                       │
│ Tickers: 5                                                            │
│ Created: 2026-01-11 14:38                                             │
│ Updated: 2026-01-11 14:39                                             │
│                                                                       │
│ AAPL, MSFT, GOOGL, NVDA, AMZN                                         │
╰───────────────────────────────────────────────────────────────────────╯
```

### Stock Universe Management

Access pre-built stock universes from major indices for batch analysis.

**Available Universes:**

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

**Example Output:**

```
                           Available Stock Universes
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Name        ┃ Description                                 ┃ Status        ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ dow30       │ Dow Jones Industrial Average - 30 Blue...   │ 30 tickers    │
│ mag7        │ Magnificent 7 - Tech megacaps               │ 7 tickers     │
│ nasdaq100   │ NASDAQ 100 - Top tech-heavy US stocks       │ Not populated │
│ sp500       │ S&P 500 - Large Cap US equities             │ Not populated │
└─────────────┴─────────────────────────────────────────────┴───────────────┘

╭────────────────────────────── Universe: mag7 ───────────────────────────────╮
│ Description: Magnificent 7 - Tech megacaps                                  │
│ Tickers: 7                                                                  │
│ Last Updated: 2026-01-11 14:57                                              │
│                                                                             │
│ Tickers:                                                                    │
│ AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA                                   │
╰─────────────────────────────────────────────────────────────────────────────╯
```

### System Commands

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

---

## Political Risk Analysis

The **Political Risk Analyst** is a specialized agent that evaluates political factors affecting investments:

### What It Analyzes

| Factor | Description |
|--------|-------------|
| **Electoral Cycles** | Upcoming elections, political transitions, government stability |
| **Government Intervention** | State ownership, price controls, political appointments |
| **Regulatory Environment** | Pending regulations, tax policy changes, licensing risks |
| **Geopolitical Factors** | Sanctions, trade wars, export market dependencies |
| **Institutional Stability** | Rule of law, regulatory independence, property rights |

### Score Interpretation

| Score Range | Interpretation |
|-------------|----------------|
| +50 to +100 | Political tailwinds (favorable policies, deregulation) |
| +10 to +49 | Slightly favorable political environment |
| -10 to +10 | Neutral political risk |
| -49 to -10 | Elevated political risk |
| -100 to -50 | High political risk (consider avoiding) |

### Example: State-Owned Companies

```bash
# Petrobras (Brazilian state oil company) - high political exposure
consilium analyze PETR3.SA --verbose

# The Political Risk Analyst will flag:
# - Electoral cycle risks
# - History of government intervention
# - Price control exposure
# - Political appointment risks
```

---

## Consensus Algorithm

The weighted consensus algorithm combines individual agent signals into a final recommendation:

### Signal Scores
| Signal | Score |
|--------|-------|
| STRONG_BUY | +100 |
| BUY | +50 |
| HOLD | 0 |
| SELL | -50 |
| STRONG_SELL | -100 |

### Confidence Multipliers
| Confidence | Multiplier |
|------------|------------|
| VERY_HIGH | 1.0 |
| HIGH | 0.85 |
| MEDIUM | 0.7 |
| LOW | 0.5 |
| VERY_LOW | 0.3 |

### Calculation

```
weighted_score = Σ(signal_score × agent_weight × confidence_mult) / Σ(weight × conf)
```

### Final Signal Thresholds
| Condition | Signal |
|-----------|--------|
| score ≥ 60 | STRONG_BUY |
| score ≥ 20 | BUY |
| score > -20 | HOLD |
| score > -60 | SELL |
| score ≤ -60 | STRONG_SELL |

---

## Example Output

```
╭────────────────────────────── Analysis Request ──────────────────────────────╮
│ Analyzing: AAPL                                                              │
│ Agents: All (13 investors + 7 specialists)                                   │
│ Specialists: Enabled                                                         │
╰──────────────────────────────────────────────────────────────────────────────╯

╭────────────────────────────────── Summary ───────────────────────────────────╮
│ Consilium Analysis Complete                                                  │
│ Tickers: AAPL                                                                │
│ Agents: 20 | Time: 45.2s                                                     │
╰──────────────────────────────────────────────────────────────────────────────╯

╭──────────────────────────── Consensus: AAPL ─────────────────────────────────╮
│ AAPL                                                                         │
│                                                                              │
│ Signal: BUY                                                                  │
│ Confidence: HIGH                                                             │
│ Score: 42.3                                                                  │
│                                                                              │
│ Votes: 8 Buy | 3 Hold | 2 Sell                                               │
│ Agreement: 62%                                                               │
╰──────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────────────────────────────────────────────╮
│ Key Themes                                                                   │
│   - Strong ecosystem and customer loyalty (economic moat)                    │
│   - Services segment driving high-margin recurring revenue                   │
│   - Exceptional cash flow generation supports buybacks                       │
╰──────────────────────────────────────────────────────────────────────────────╯
╭──────────────────────────────────────────────────────────────────────────────╮
│ Risks                                                                        │
│   - iPhone sales deceleration in mature markets                              │
│   - China exposure and regulatory headwinds                                  │
│   - Valuation premium limits upside potential                                │
╰──────────────────────────────────────────────────────────────────────────────╯
```

---

## Architecture

```
consilium/
├── cli.py                 # Typer CLI application
├── config.py              # Pydantic Settings configuration
├── core/
│   ├── models.py          # Stock, AgentResponse, ConsensusResult
│   ├── enums.py           # SignalType, ConfidenceLevel, etc.
│   └── exceptions.py      # Custom exception hierarchy
├── data/
│   ├── yahoo.py           # Yahoo Finance data provider
│   ├── cache.py           # Cache-aside pattern with MySQL
│   └── universes.py       # Stock universe data provider
├── db/
│   ├── connection.py      # Async MySQL connection pool
│   ├── migrations.py      # Schema DDL (versioned migrations)
│   └── repository.py      # Data access layer
├── agents/
│   ├── base.py            # BaseAgent, InvestorAgent, SpecialistAgent
│   └── registry.py        # Agent factory and discovery
├── prompts/
│   ├── investors/         # 13 investor personality YAMLs
│   └── specialists/       # 7 specialist analysis YAMLs
├── llm/
│   ├── client.py          # Async Anthropic client with retry
│   └── prompts.py         # Prompt builder with templates
├── analysis/
│   ├── orchestrator.py    # Multi-agent pipeline coordination
│   └── consensus.py       # Weighted voting algorithm
└── output/
    ├── formatters.py      # Rich tables and panels
    └── exporters.py       # JSON, CSV, MD export
```

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

---

## Database Schema

Consilium uses MySQL with versioned migrations:

```bash
# Check current schema version
consilium db status

# Apply pending migrations
consilium db init
```

### Tables

| Table | Purpose |
|-------|---------|
| `analysis_history` | All analysis results with consensus |
| `agent_responses` | Individual agent recommendations |
| `specialist_reports` | Specialist analysis reports |
| `market_data_cache` | Cached Yahoo Finance data |
| `watchlists` | User-defined stock lists |
| `stock_universes` | Pre-built index universes (S&P 500, etc.) |
| `price_history` | Historical price data (for backtesting) |
| `schema_versions` | Migration tracking |

---

## Tech Stack

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
- [ ] Backtesting engine
- [ ] Portfolio optimization recommendations
- [ ] Screening based on agent criteria
- [ ] Web dashboard interface
- [ ] Slack/Discord integration for alerts
- [ ] Custom agent personality creation

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
