# Oracle Member Verification Bot

A **Discord bot** built with [discord.py](https://discordpy.readthedocs.io/) to automate **member verification and registration** using reactions, DMs, and an Excel-based database.

---

## 🔑 Features
- ✅ **Reaction-based verification** → members react with 🙏 to begin verification.  
- 📩 **DM form input** → users provide `email, nama lengkap, tanggal lahir(dd-mm-yyyy), nickname`.  
- 📝 **Excel database integration** → stores and updates member data in an `.xlsx` file.  
- 🎫 **Automatic member number generation** → assigns sequential `OTM-XXX` IDs starting from 112.  
- 🔄 **Smart updates** → detects existing data and allows users to confirm or update their information.  
- 🎉 **Welcome messages** → greets verified members in a public channel.  
- 🏷️ **Role management** → assigns a verified role and removes temporary roles.  
- 🛠️ **Admin command** → `!sendverify` posts a verification message in the verification channel.  
- 📑 **Logging** → detailed logs saved in `discord.log`.

---

## ⚙️ Tech Stack
- Python 3.10+  
- [discord.py](https://github.com/Rapptz/discord.py)  
- [pandas](https://pandas.pydata.org/)  
- [openpyxl](https://openpyxl.readthedocs.io/)  
- [python-dotenv](https://pypi.org/project/python-dotenv/)  

---

## 📂 Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/oracle-member-verification-bot.git
cd oracle-member-verification-bot
