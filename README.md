# Mark 4 - Tactical Telegram Bot 🦾

A high-performance Windows management bot for remote control, system monitoring, and automated UMS interactions.

## 🚀 Features

-   **Remote Unlock**: Advanced bypass for Windows Secure Desktop via Task Scheduler & VBS Bridge.
-   **System Monitoring**: Real-time CPU/GPU telemetry, thermal watchdog, and battery alerts.
-   **Media Control**: Volume, Brightness, and Media Playback management.
-   **UMS Automation**: Automated login and attendance tracking for LPU UMS portal.
-   **Chrome Management**: Remote profile switching and tab control.
-   **Agentic AI**: Integrated with Google Gemini for natural language command processing.
-   **Hardware Emulation**: Support for Unified Remote HID driver for secure input injection.

## 🛠️ Setup

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/YOUR_USERNAME/Mark4-Bot.git
    cd Mark4-Bot
    ```

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment**:
    -   Copy `.env.example` to `.env`.
    -   Fill in your `TELEGRAM_TOKEN`, `GEMINI_API_KEY`, and `ALLOWED_USER_IDS`.
    -   (Optional) Add your `UMS_USERNAME` and `UMS_PASSWORD`.

4.  **Run the Bot**:
    ```bash
    python telegram_command_bot.py
    ```

## 🛡️ Security

-   The bot only responds to User IDs listed in `ALLOWED_USER_IDS`.
-   Sensitive credentials are managed via environment variables.
-   Administrative privileges are required for some unlock functions.

## ⚖️ License

MIT License.
