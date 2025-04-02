# PEER - P2P Marketplace Application

PEER (P2P Electronic Exchange Resource) is a simple peer-to-peer marketplace application built with Python and Flask. This application allows users to buy and sell products or services directly with each other.

## Features

- User authentication (sign up, login, logout)
- Mobile-friendly responsive design
- Two primary roles: Buyers and Sellers
- Product/service listing creation with:
  - Title, description, type (product/service)
  - Flexible payment methods (cash, bank, UPI, or custom)
  - Timeline options for delivery/completion
  - Preview functionality with 10-second confirmation timer
- Search functionality
- Order management
- Real-time chat between buyers and sellers
- Order history tracking
- Complaint resolution system

## Installation

1. Clone the repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Run the application:

```bash
python app.py
```

4. Access the application in your browser at `http://localhost:5000`

## Tech Stack

- **Backend**: Python, Flask
- **Database**: SQLAlchemy with SQLite
- **Frontend**: HTML, CSS, JavaScript
- **UI Design**: Modern, smooth design with violet and sky blue color scheme

## Usage

### As a Seller:
1. Create an account or log in
2. Navigate to the "Sell" section
3. Create a post for your product or service
4. Set payment methods and timeline options
5. Manage your orders and communicate with buyers

### As a Buyer:
1. Create an account or log in
2. Browse available products/services
3. Search for specific items
4. Place orders
5. Communicate with sellers through the built-in chat

## Directory Structure

```
/ (root)
│
├── app/
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   │       └── main.js
│   │
│   └── templates/
│       ├── layout.html
│       ├── index.html
│       ├── login.html
│       ├── signup.html
│       ├── dashboard.html
│       ├── buyer.html
│       ├── seller.html
│       ├── create_post.html
│       ├── post_detail.html
│       ├── order_detail.html
│       ├── order_history.html
│       └── search_results.html
│
├── app.py
├── requirements.txt
└── README.md
``` 