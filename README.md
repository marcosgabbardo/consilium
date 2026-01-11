# Consilium

**Multi-Agent Investment Analysis CLI** — Harness the wisdom of legendary investors through AI-powered stock analysis.

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/anthropic-claude--opus--4.5-purple.svg" alt="Claude Opus 4.5">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
</p>

---

## Overview

Consilium simulates a **hedge fund investment committee** where 18 specialized AI agents—each embodying the investment philosophy of legendary investors like Warren Buffett, Charlie Munger, and Peter Lynch—analyze stocks and reach a weighted consensus.

The name comes from Latin *consilium* ("council" or "deliberation"), reflecting the collaborative decision-making process at the heart of the system.

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    consilium analyze AAPL                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              1. MARKET DATA (Yahoo Finance)                  │
│                   Price, fundamentals, technicals            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              2. SPECIALIST ANALYSIS (Parallel)               │
│     Valuation │ Fundamentals │ Technicals │ Sentiment        │
│                      Risk │ Portfolio                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              3. INVESTOR ANALYSIS (Parallel)                 │
│  Buffett │ Munger │ Graham │ Lynch │ Burry │ Damodaran │...  │
│         Each applies their unique investment philosophy      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 4. WEIGHTED CONSENSUS                        │
│              Final signal with confidence score              │
└─────────────────────────────────────────────────────────────┘
```

---

## Features

- **12 Investor Personalities** — Each with distinct investment philosophies, from value investing to growth, momentum, and macro strategies
- **6 Specialist Agents** — Quantitative analysis covering valuation, fundamentals, technicals, sentiment, risk, and portfolio fit
- **Weighted Consensus Algorithm** — Agents vote with configurable weights and confidence levels
- **Parallel Execution** — Async architecture for fast multi-agent analysis
- **Rich CLI Output** — Beautiful tables and panels with detailed reasoning
- **Export Formats** — JSON, CSV, and Markdown reports
- **MySQL Caching** — Smart caching of market data with configurable TTLs

---

## The Investment Committee

### Investor Agents

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

### Specialist Agents

| Specialist | Focus |
|------------|-------|
| **Valuation Analyst** | DCF, comparables, intrinsic value estimation |
| **Fundamentals Analyst** | Financial statements, profitability, balance sheet strength |
| **Technical Analyst** | Price patterns, momentum indicators, support/resistance |
| **Sentiment Analyst** | Market sentiment, institutional positioning, contrarian signals |
| **Risk Manager** | Volatility, drawdown potential, systematic vs idiosyncratic risk |
| **Portfolio Manager** | Position sizing, entry strategy, portfolio fit |

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
```

### Database Setup

```bash
# Create database
mysql -u root -p -e "CREATE DATABASE consilium;"
mysql -u root -p -e "CREATE USER 'consilium'@'localhost' IDENTIFIED BY 'your_password';"
mysql -u root -p -e "GRANT ALL PRIVILEGES ON consilium.* TO 'consilium'@'localhost';"

# Initialize schema
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

### Filter Agents

```bash
# Use only specific investors
consilium analyze TSLA --agents buffett,munger,burry

# Skip specialist analysis (faster)
consilium analyze AAPL --skip-specialists
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

# Agent details
consilium agents info buffett
```

### System Commands

```bash
# Check configuration status
consilium status

# Database status
consilium db status

# Show version
consilium --version
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
╭─────────────────────────────────────────────────────────────╮
│                    Analysis: AAPL                           │
├─────────────────────────────────────────────────────────────┤
│  Signal: BUY          Confidence: HIGH                      │
│  Score: +42.3         Votes: 8 Buy | 3 Hold | 1 Sell        │
├─────────────────────────────────────────────────────────────┤
│  Key Themes:                                                │
│  • Strong ecosystem and customer loyalty (moat)             │
│  • Services segment driving recurring revenue               │
│  • Valuation stretched relative to growth                   │
│  • China exposure and regulatory risks                      │
╰─────────────────────────────────────────────────────────────╯
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
│   └── cache.py           # Cache-aside pattern with MySQL
├── db/
│   ├── connection.py      # Async MySQL connection pool
│   └── migrations.py      # Schema DDL
├── agents/
│   ├── base.py            # BaseAgent, InvestorAgent, SpecialistAgent
│   ├── registry.py        # Agent factory and discovery
│   ├── investors/         # 12 investor personality agents
│   └── specialists/       # 6 specialist analysis agents
├── llm/
│   ├── client.py          # Async Anthropic client with retry
│   ├── prompts.py         # Prompt templates
│   └── schemas.py         # JSON schemas for structured output
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
CONSILIUM_WEIGHT_BUFFETT=2.0   # Legendary track record
CONSILIUM_WEIGHT_MUNGER=1.8    # Partner to Buffett
CONSILIUM_WEIGHT_GRAHAM=1.5    # Father of value investing
CONSILIUM_WEIGHT_WOOD=1.0      # Growth/innovation focus
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

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| CLI Framework | Typer + Rich |
| LLM | Anthropic Claude Opus 4.5 |
| Market Data | Yahoo Finance |
| Data Validation | Pydantic v2 |
| Database | MySQL (aiomysql) |
| Async Runtime | asyncio |

---

## Roadmap

- [ ] Watchlist management with scheduled analysis
- [ ] Historical analysis tracking and backtesting
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
