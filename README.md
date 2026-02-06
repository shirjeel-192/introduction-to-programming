# 📊 Crypto Trend Tracker (Group 4)

**Crypto Trend Tracker** is a powerful analytics dashboard designed to identify "hidden gems" in the cryptocurrency market. Unlike traditional trackers that focus solely on price or market cap, this tool ranks coins by their **Volume/Market Cap Ratio**, highlighting assets with unusually high trading activity relative to their size.

---

## 🚀 Features

- **Custom Trend Metric**: Ranks top 1000 coins by Volume/Market Cap ratio to find breakouts.
- **Stablecoin Filtering**: Toggle to exclude over 50+ stablecoins (USDT, USDC, etc.) for clearer signal.
- **Interactive Multi-Coin Comparison**: Select up to 5 coins directly from the table to overlay their performance (Price, Volume, Ratio) on a shared timeline.
- **Historical Analysis**: "Time Travel" through data snapshots to see what was trending in the past.
- **Live Updates**: Data is updated twice daily via automated pipelines.

---

## 🛠 Architecture

The project consists of two main components:

1. **Data Pipeline (`fetch_crypto_data.py`)**:

   * Fetches top 1000 cryptocurrencies from CoinGecko API.
   * Calculates the `Vol/MCap Ratio`.
   * Uploads data to a Supabase (PostgreSQL) database.
   * Runs automatically via GitLab CI/CD schedules.
2. **Frontend Dashboard (`app.py`)**:

   * Built with **Streamlit** for rapid, interactive UI.
   * Connects to Supabase to fetch live and historical snapshots.
   * Visualizes trends using **Plotly**.

---

## 📋 Prerequisites

- **Python 3.10+**
- A **Supabase** project (URL and Key)
- (Optional) **CoinGecko API Key** (Free tier works, but pro is recommended for higher limits)

---

## ⚙️ Installation

1. **Clone the repository**:

   ```bash
   git clone https://zivgitlab.uni-muenster.de/cvmls/itsp-2025/group-4.git
   cd group-4
   ```
2. **Create a virtual environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```
4. **Set up environment variables**:
   Create a `.env` file in the root directory:

   ```ini
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_anon_key
   COINGECKO_API_KEY=your_coingecko_key  # Optional for frontend, required for pipeline
   ```

---

## 🖥 Usage

### Running the Dashboard

Start the Streamlit app locally:

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

### Running the Data Pipeline (Manual)

To manually fetch fresh data and update the database:

```bash
python fetch_crypto_data.py
```

---

## 🧩 Visuals

### Main Dashboard

See the top movers, summary metrics, and the main trending table.

### Comparison Mode

Select coins from the table to compare them in the interactive chart.

---

## 🛣 Roadmap

- [X] Initial MVP with Vol/MCap ranking
- [X] Automated Data Pipeline (GitLab CI)
- [X] Comparison Charts & Historical Snapshots
- [ ] **Advanced Metrics**: RSI and Moving Averages
- [ ] **Alerts**: Email notifications for sudden ratio spikes
- [ ] **User Accounts**: Save favorite coins and custom watchlists

---

## 🤝 Contributing

Contributions are welcome! Here's how to help:

1. **Fork** the project.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. **Commit** your changes (`git commit -m 'Add some AmazingFeature'`).
4. **Push** to the branch (`git push origin feature/AmazingFeature`).
5. Open a **Merge Request**.

---

## ✍️ Authors

**Group 4 - ITSP 2025**

- **Shirjeel Ahmed**
- **Lilas Almahdi**

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Built with ❤️ at the University of Münster.*
