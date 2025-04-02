from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_socketio import SocketIO, emit, join_room
import os
from wallet_service import WalletService, start_monitoring, stop_monitoring, complete_order_blockchain
from flask_migrate import Migrate

app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
app.config['SECRET_KEY'] = 'peer-app-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///peer.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['USE_REAL_BLOCKCHAIN'] = os.environ.get('USE_REAL_BLOCKCHAIN', 'False')

db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app)

# Initialize wallet service
wallet_service = WalletService(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_verified = db.Column(db.Boolean, default=False)  # KYC verification status
    verification_date = db.Column(db.DateTime, nullable=True)  # When the user was verified
    reputation_score = db.Column(db.Float, default=0.0)  # User reputation score
    phone_number = db.Column(db.String(20), nullable=True)  # User phone number
    dob = db.Column(db.Date, nullable=True)  # Date of birth
    location = db.Column(db.String(100), nullable=True)  # User's location/country
    posts = db.relationship('Post', backref='seller', lazy=True)
    orders = db.relationship('Order', backref='buyer', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    post_type = db.Column(db.String(20), nullable=False)  # 'product' or 'service'
    payment_method = db.Column(db.String(50), nullable=False)
    custom_payment = db.Column(db.String(100), nullable=True)
    timeline_options = db.Column(db.String(200), nullable=False)  # Comma-separated options
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_boosted = db.Column(db.Boolean, default=False)  # Whether the post is boosted
    boost_expires_at = db.Column(db.DateTime, nullable=True)  # When the boost expires
    is_draft = db.Column(db.Boolean, default=False)  # Whether the post is a draft
    orders = db.relationship('Order', backref='post', lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    timeline_selected = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, canceled, disputed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    buyer_confirmed = db.Column(db.Boolean, default=False)
    seller_confirmed = db.Column(db.Boolean, default=False)
    messages = db.relationship('Message', backref='order', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='messages')

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='notifications')
    order = db.relationship('Order', backref='notifications')

class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    address = db.Column(db.String(42), nullable=False, unique=True)  # BEP20 address (42 chars with 0x prefix)
    encrypted_private_key = db.Column(db.Text, nullable=False)  # Encrypted private key
    balance = db.Column(db.String(30), default="0")  # Store as string to avoid floating point issues
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('wallet', uselist=False))
    transactions = db.relationship('Transaction', backref='wallet', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'), nullable=False)
    tx_hash = db.Column(db.String(66), nullable=False, unique=True)  # Transaction hash
    amount = db.Column(db.String(30), nullable=False)  # Amount of USDT
    tx_type = db.Column(db.String(10), nullable=False)  # 'send' or 'receive'
    status = db.Column(db.String(20), default='pending')  # 'pending', 'completed', 'failed'
    to_address = db.Column(db.String(42), nullable=True)  # Destination address for 'send'
    from_address = db.Column(db.String(42), nullable=True)  # Source address for 'receive'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    block_number = db.Column(db.Integer, nullable=True)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 star rating
    comment = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=True)  # Response from the recipient
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], backref='reviews_given')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='reviews_received')
    order = db.relationship('Order', backref='reviews')

# Socket.IO events
@socketio.on('join')
def on_join(data):
    room = str(data['order_id'])
    join_room(room)
    print(f"User joined room: {room}")

@socketio.on('join_notifications')
def on_join_notifications(data):
    user_id = data['user_id']
    room = f"user_{user_id}_notifications"
    join_room(room)
    print(f"User joined notifications room: {room}")

@socketio.on('send_message')
def handle_message(data):
    order_id = data['order_id']
    user_id = data['user_id']
    content = data['message']
    
    # Save message to database
    new_message = Message(
        order_id=order_id,
        user_id=user_id,
        content=content,
        created_at=datetime.utcnow()
    )
    
    db.session.add(new_message)
    db.session.commit()
    
    # Get the user information for the response
    user = User.query.get(user_id)
    
    # Broadcast message to the room (order_id)
    emit('new_message', {
        'id': new_message.id,
        'user_id': user_id,
        'username': user.username,
        'content': content,
        'time': new_message.created_at.strftime('%Y-%m-%d %H:%M')
    }, to=str(order_id))

# Make current user available to all templates
@app.context_processor
def inject_user():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        return {'current_user': user}
    return {'current_user': None}

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if user exists
        user_exists = User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first()
        if user_exists:
            flash('Username or email already exists')
            return redirect(url_for('signup'))
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password, method='sha256')
        )
        db.session.add(new_user)
        db.session.commit()
        
        # Create wallet for the new user
        try:
            wallet_data = wallet_service.create_wallet()
            new_wallet = Wallet(
                user_id=new_user.id,
                address=wallet_data['address'],
                encrypted_private_key=wallet_data['encrypted_private_key'],
                balance="0"
            )
            db.session.add(new_wallet)
            db.session.commit()
        except Exception as e:
            print(f"Error creating wallet: {e}")
            # If wallet creation fails, still allow user to sign up
        
        session['user_id'] = new_user.id
        return redirect(url_for('buyer_dashboard'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash('Please check your login details and try again.')
            return redirect(url_for('login'))
        
        session['user_id'] = user.id
        return redirect(url_for('buyer_dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    posts = Post.query.filter_by(seller_id=user.id).order_by(Post.created_at.desc()).all()
    buyer_orders = Order.query.filter_by(buyer_id=user.id).order_by(Order.created_at.desc()).all()
    seller_orders = Order.query.join(Post).filter(Post.seller_id == user.id).order_by(Order.created_at.desc()).all()
    
    # Calculate reputation metrics
    reviews_received = Review.query.filter_by(recipient_id=user.id).all()
    total_reviews = len(reviews_received)
    
    if total_reviews > 0:
        avg_rating = sum(review.rating for review in reviews_received) / total_reviews
        reputation_score = round(avg_rating, 1)
    else:
        reputation_score = 0
    
    # Calculate seller and buyer ratings separately
    seller_reviews = [r for r in reviews_received if r.order and r.order.post.seller_id == user.id]
    buyer_reviews = [r for r in reviews_received if r.order and r.order.buyer_id == user.id]
    
    seller_rating = round(sum(r.rating for r in seller_reviews) / len(seller_reviews), 1) if seller_reviews else 0
    buyer_rating = round(sum(r.rating for r in buyer_reviews) / len(buyer_reviews), 1) if buyer_reviews else 0
    
    seller_rating_percentage = int(seller_rating / 5 * 100) if seller_rating else 0
    buyer_rating_percentage = int(buyer_rating / 5 * 100) if buyer_rating else 0
    
    return render_template(
        'profile.html', 
        user=user, 
        posts=posts, 
        buyer_orders=buyer_orders, 
        seller_orders=seller_orders,
        reviews_received=reviews_received,
        reviews_given=Review.query.filter_by(reviewer_id=user.id).all(),
        total_reviews=total_reviews,
        reputation_score=reputation_score,
        seller_rating=seller_rating,
        buyer_rating=buyer_rating,
        seller_rating_percentage=seller_rating_percentage,
        buyer_rating_percentage=buyer_rating_percentage
    )

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    return render_template('dashboard.html', user=user)

@app.route('/buyer')
def buyer_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get filter parameters from request
    post_type = request.args.get('post_type')
    payment_method = request.args.get('payment_method')
    search_query = request.args.get('search', '')
    
    try:
        # Try to query with boosted posts handling
        # Start with basic query for non-draft posts
        query = Post.query.filter(Post.is_draft == False)
        
        # Apply filters if they exist
        if post_type and post_type in ['product', 'service']:
            query = query.filter(Post.post_type == post_type)
        
        if payment_method and payment_method in ['bank', 'cash', 'upi', 'usdt']:
            query = query.filter(Post.payment_method == payment_method)
        
        # Apply search filter if provided
        if search_query:
            query = query.filter(
                (Post.title.contains(search_query)) | 
                (Post.description.contains(search_query))
            )
        
        # Get current time for checking boost expiration
        current_time = datetime.utcnow()
        
        # Get all posts matching the criteria
        all_posts = query.all()
        
        # Separate boosted and non-boosted posts
        boosted_posts = []
        normal_posts = []
        
        for post in all_posts:
            # Check if post is still boosted (boost hasn't expired)
            if post.is_boosted and post.boost_expires_at and post.boost_expires_at > current_time:
                boosted_posts.append(post)
            else:
                # If boost has expired, update the database
                if post.is_boosted and post.boost_expires_at and post.boost_expires_at <= current_time:
                    post.is_boosted = False
                    post.boost_expires_at = None
                    db.session.commit()
                normal_posts.append(post)
        
        # Sort normal posts by most recent
        normal_posts.sort(key=lambda x: x.created_at, reverse=True)
        
        # Sort boosted posts by most recent as well
        boosted_posts.sort(key=lambda x: x.created_at, reverse=True)
        
        # Combine the posts with boosted posts first
        posts = boosted_posts + normal_posts
        
    except Exception as e:
        # If columns don't exist yet, use a simpler query without boost handling
        print(f"Error querying with boost filters: {e}")
        
        # Start with basic query
        query = Post.query
        
        # Apply filters if they exist
        if post_type and post_type in ['product', 'service']:
            query = query.filter(Post.post_type == post_type)
        
        if payment_method and payment_method in ['bank', 'cash', 'upi', 'usdt']:
            query = query.filter(Post.payment_method == payment_method)
        
        # Apply search filter if provided
        if search_query:
            query = query.filter(
                (Post.title.contains(search_query)) | 
                (Post.description.contains(search_query))
            )
        
        # Get all posts
        posts = query.order_by(Post.created_at.desc()).all()
        
        # Add missing attributes to each post
        for post in posts:
            post.is_boosted = False
            post.boost_expires_at = None
    
    return render_template('buyer.html', posts=posts)

@app.route('/seller')
def seller_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    try:
        # Try to query posts with boost and draft flags
        posts = Post.query.filter_by(seller_id=user.id).order_by(Post.created_at.desc()).all()
    except Exception as e:
        # If columns don't exist yet, use a simpler query
        print(f"Error querying posts: {e}")
        # This will run if the column doesn't exist yet
        posts = db.session.query(Post.id, Post.title, Post.description, Post.post_type, 
                               Post.payment_method, Post.custom_payment, Post.timeline_options,
                               Post.seller_id, Post.created_at) \
                        .filter(Post.seller_id == user.id) \
                        .order_by(Post.created_at.desc()) \
                        .all()
        
        # Add missing attributes to each post object
        for post in posts:
            post.is_boosted = False
            post.is_draft = False
    
    return render_template('seller.html', posts=posts, user=user)

@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        post_type = request.form.get('post_type')
        payment_method = request.form.get('payment_method')
        custom_payment = request.form.get('custom_payment')
        timeline_options = request.form.get('timeline_options')
        price = request.form.get('price', '0')
        location = request.form.get('location', '')
        payment_terms = request.form.get('payment_terms', '')
        is_draft = request.form.get('is_draft') == 'true'
        
        # Handle boost option
        is_boosted = request.form.get('boost_listing') == 'on'
        boost_expires_at = None
        
        # Check wallet balance before processing boost payment
        if is_boosted:
            user = User.query.get(session['user_id'])
            wallet = Wallet.query.filter_by(user_id=user.id).first()
            
            if not wallet or float(wallet.balance) < 10:
                flash('Insufficient funds to boost listing. You need at least 10 USDT.', 'error')
                is_boosted = False
            else:
                # Set boost expiry date (7 days from now)
                boost_expires_at = datetime.utcnow() + timedelta(days=7)
                
                # Deduct 10 USDT from wallet
                new_balance = float(wallet.balance) - 10
                wallet.balance = str(new_balance)
                db.session.commit()
                
                # Create a transaction record for the boost payment
                new_transaction = Transaction(
                    wallet_id=wallet.id,
                    tx_hash=f"boost-{datetime.utcnow().timestamp()}-{session['user_id']}",
                    amount="10",
                    tx_type="boost",
                    status="completed",
                    to_address="PEER_PLATFORM"  # Platform wallet address would go here
                )
                db.session.add(new_transaction)
                db.session.commit()
                
                flash('Your listing has been boosted and will appear at the top of search results for 7 days!', 'success')
        
        # Create new post
        new_post = Post(
            title=title,
            description=description,
            post_type=post_type,
            payment_method=payment_method,
            custom_payment=custom_payment if payment_method == 'other' else None,
            timeline_options=timeline_options,
            seller_id=session['user_id'],
            is_boosted=is_boosted,
            boost_expires_at=boost_expires_at,
            is_draft=is_draft
        )
        
        db.session.add(new_post)
        db.session.commit()
        
        if is_draft:
            flash('Your draft has been saved.', 'success')
        else:
            flash('Your post has been created successfully!', 'success')
        
        return redirect(url_for('seller_dashboard'))
    
    return render_template('create_post.html')

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post_detail.html', post=post)

@app.route('/create_order/<int:post_id>', methods=['POST'])
def create_order(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    post = Post.query.get_or_404(post_id)
    timeline = request.form.get('timeline')
    
    # Check if the buyer has enough funds
    buyer = User.query.get(session['user_id'])
    buyer_wallet = Wallet.query.filter_by(user_id=buyer.id).first()
    
    # Parse the actual quantity from the post description
    # Example format: "USDT Quantity: 1.3, Price per USDT: 96"
    required_funds = 0
    if "USDT Quantity:" in post.description:
        try:
            quantity_text = post.description.split("USDT Quantity:")[1].split(",")[0].strip()
            required_funds = float(quantity_text)
        except (IndexError, ValueError):
            # Fallback to the minimum value
            required_funds = 1.0
    else:
        # Default value if parsing fails
        required_funds = 1.0
    
    if not buyer_wallet or float(buyer_wallet.balance) < required_funds:
        flash(f'Insufficient funds in your wallet. You need at least {required_funds} USDT before placing an order.', 'error')
        return redirect(url_for('post_detail', post_id=post_id))
    
    new_order = Order(
        buyer_id=session['user_id'],
        post_id=post_id,
        timeline_selected=timeline,
        status='pending',
        buyer_confirmed=False,
        seller_confirmed=False
    )
    
    db.session.add(new_order)
    db.session.commit()
    
    # Create notification for the seller
    seller_notification = Notification(
        user_id=post.seller_id,
        order_id=new_order.id,
        content=f"New order from {buyer.username} for your post '{post.title}'"
    )
    db.session.add(seller_notification)
    db.session.commit()
    
    # Emit notification event via Socket.IO
    seller_room = f"user_{post.seller_id}_notifications"
    socketio.emit('new_notification', {
        'notification_id': seller_notification.id,
        'content': seller_notification.content,
        'order_id': new_order.id,
        'time': seller_notification.created_at.strftime('%Y-%m-%d %H:%M')
    }, to=seller_room)
    
    return redirect(url_for('order_detail', order_id=new_order.id))

@app.route('/order/<int:order_id>')
def order_detail(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    messages = Message.query.filter_by(order_id=order_id).order_by(Message.created_at).all()
    
    return render_template('order_detail.html', order=order, messages=messages)

@app.route('/update_order_status/<int:order_id>', methods=['GET', 'POST'])
def update_order_status(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    
    # Get status either from form data (POST) or query parameters (GET)
    if request.method == 'POST':
        status = request.form.get('status')
    else:
        status = request.args.get('status')
    
    # Verify user has permission to update status
    user_id = session['user_id']
    if user_id != order.buyer_id and user_id != order.post.seller_id:
        flash('You do not have permission to update this order')
        return redirect(url_for('order_detail', order_id=order_id))
    
    # Handle the different status values
    if status == 'buyer_confirmed':
        if user_id != order.buyer_id:
            flash('Only the buyer can confirm completion')
            return redirect(url_for('order_detail', order_id=order_id))
            
        order.buyer_confirmed = True
        db.session.commit()
        
        # Notify seller that buyer has confirmed
        notification = Notification(
            user_id=order.post.seller_id,
            order_id=order_id,
            content=f"Buyer has confirmed completion of order for '{order.post.title}'"
        )
        db.session.add(notification)
        db.session.commit()
        
        # Check if both parties have confirmed
        if order.seller_confirmed:
            # Complete the order
            return complete_order(order)
        else:
            flash('You have confirmed completion. Waiting for the seller to confirm.')
            
    elif status == 'seller_confirmed':
        if user_id != order.post.seller_id:
            flash('Only the seller can confirm completion')
            return redirect(url_for('order_detail', order_id=order_id))
            
        order.seller_confirmed = True
        db.session.commit()
        
        # Notify buyer that seller has confirmed
        notification = Notification(
            user_id=order.buyer_id,
            order_id=order_id,
            content=f"Seller has confirmed completion of order for '{order.post.title}'"
        )
        db.session.add(notification)
        db.session.commit()
        
        # Check if both parties have confirmed
        if order.buyer_confirmed:
            # Complete the order
            return complete_order(order)
        else:
            flash('You have confirmed completion. Waiting for the buyer to confirm.')
    
    # Handle traditional status values
    elif status in ['completed', 'canceled', 'disputed']:
        order.status = status
        db.session.commit()
        
        # Create notifications for both buyer and seller
        acting_user = User.query.get(user_id)
        post_title = order.post.title
        
        # Create notification for buyer if seller is updating, or vice versa
        notify_user_id = order.buyer_id if user_id == order.post.seller_id else order.post.seller_id
        notification = Notification(
            user_id=notify_user_id,
            order_id=order_id,
            content=f"Order for '{post_title}' has been marked as {status} by {acting_user.username}"
        )
        db.session.add(notification)
        db.session.commit()
        
        # Emit notification event via Socket.IO
        notified_user_room = f"user_{notify_user_id}_notifications"
        socketio.emit('new_notification', {
            'notification_id': notification.id,
            'content': notification.content,
            'order_id': order_id,
            'time': notification.created_at.strftime('%Y-%m-%d %H:%M')
        }, to=notified_user_room)
        
        flash(f'Order has been marked as {status}')
    
    return redirect(url_for('order_detail', order_id=order_id))

def complete_order(order):
    """Complete the order and transfer funds from buyer to seller"""
    order.status = 'completed'
    
    # Get buyer and seller wallets
    buyer_wallet = Wallet.query.filter_by(user_id=order.buyer_id).first()
    seller_wallet = Wallet.query.filter_by(user_id=order.post.seller_id).first()
    
    if buyer_wallet and seller_wallet:
        try:
            # Use blockchain transfers in production mode, simulate in demo mode
            if app.config['USE_REAL_BLOCKCHAIN'] == 'True':
                # Use the blockchain service for real transfers
                result = complete_order_blockchain(order, buyer_wallet, seller_wallet)
                
                # Create notifications for both parties
                buyer_notification = Notification(
                    user_id=order.buyer_id,
                    order_id=order.id,
                    content=f"Order completed! Transaction hash: {result['tx_hash']}"
                )
                db.session.add(buyer_notification)
                
                seller_notification = Notification(
                    user_id=order.post.seller_id,
                    order_id=order.id,
                    content=f"Order completed! You received payment. Transaction hash: {result['tx_hash']}"
                )
                db.session.add(seller_notification)
                db.session.commit()
                
                flash('Order completed successfully! The blockchain transaction has been submitted.')
            else:
                # Parse the actual amount from the post description
                amount = 0
                if "USDT Quantity:" in order.post.description:
                    try:
                        quantity_text = order.post.description.split("USDT Quantity:")[1].split(",")[0].strip()
                        amount = float(quantity_text)
                    except (IndexError, ValueError):
                        # Fallback to the minimum value
                        amount = 1.0
                else:
                    # Default value if parsing fails
                    amount = 1.0
                
                # Check if buyer has enough funds
                if float(buyer_wallet.balance) >= amount:
                    # Deduct from buyer's wallet
                    buyer_wallet.balance = str(float(buyer_wallet.balance) - amount)
                    
                    # Add to seller's wallet
                    seller_wallet.balance = str(float(seller_wallet.balance) + amount)
                    
                    # Generate unique timestamps for each transaction
                    timestamp = datetime.utcnow().timestamp()
                    buyer_timestamp = timestamp
                    seller_timestamp = timestamp + 0.1  # Add 0.1 seconds to ensure uniqueness
                    
                    # Create transaction record for buyer (outgoing)
                    transaction = Transaction(
                        wallet_id=buyer_wallet.id,
                        tx_hash=f"order-{order.id}-send-{buyer_timestamp}",
                        amount=str(amount),
                        tx_type="send",
                        status="completed",
                        to_address=seller_wallet.address
                    )
                    db.session.add(transaction)
                    
                    # Create corresponding transaction for seller (incoming)
                    seller_transaction = Transaction(
                        wallet_id=seller_wallet.id,
                        tx_hash=f"order-{order.id}-receive-{seller_timestamp}",
                        amount=str(amount),
                        tx_type="receive",
                        status="completed",
                        from_address=buyer_wallet.address
                    )
                    db.session.add(seller_transaction)
                    db.session.commit()
                    
                    # Create notifications for both parties
                    buyer_notification = Notification(
                        user_id=order.buyer_id,
                        order_id=order.id,
                        content=f"Order completed! {amount} USDT has been transferred to the seller."
                    )
                    db.session.add(buyer_notification)
                    
                    seller_notification = Notification(
                        user_id=order.post.seller_id,
                        order_id=order.id,
                        content=f"Order completed! You received {amount} USDT from the buyer."
                    )
                    db.session.add(seller_notification)
                    db.session.commit()
                    
                    flash('Order completed successfully! Funds have been transferred.')
                else:
                    flash('Insufficient funds in buyer wallet to complete the order.', 'error')
                    # Reset confirmation status
                    order.buyer_confirmed = False
                    order.seller_confirmed = False
                    db.session.commit()
            
        except Exception as e:
            # Roll back session in case of error
            db.session.rollback()
            flash(f'Error processing payment: {str(e)}', 'error')
            # Reset confirmation status
            order.buyer_confirmed = False
            order.seller_confirmed = False
            db.session.commit()
    else:
        flash('Could not process payment: missing wallet information', 'error')
        # Reset confirmation status
        order.buyer_confirmed = False
        order.seller_confirmed = False
        db.session.commit()
    
    return redirect(url_for('order_detail', order_id=order.id))

@app.route('/send_message/<int:order_id>', methods=['POST'])
def send_message(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    content = request.form.get('content')
    
    new_message = Message(
        order_id=order_id,
        user_id=session['user_id'],
        content=content
    )
    
    db.session.add(new_message)
    db.session.commit()
    
    return redirect(url_for('order_detail', order_id=order_id))

@app.route('/file_complaint/<int:order_id>', methods=['POST'])
def file_complaint(order_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    content = request.form.get('content')
    
    new_complaint = Complaint(
        order_id=order_id,
        user_id=session['user_id'],
        content=content
    )
    
    db.session.add(new_complaint)
    db.session.commit()
    
    flash('Your complaint has been filed')
    return redirect(url_for('order_detail', order_id=order_id))

@app.route('/search')
def search():
    query = request.args.get('query', '')
    
    posts = Post.query.filter(
        (Post.title.contains(query)) | 
        (Post.description.contains(query))
    ).all()
    
    return render_template('search_results.html', posts=posts, query=query)

@app.route('/order_history')
def order_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    buyer_orders = Order.query.filter_by(buyer_id=user_id).all()
    seller_orders = Order.query.join(Post).filter(Post.seller_id == user_id).all()
    
    return render_template('order_history.html', buyer_orders=buyer_orders, seller_orders=seller_orders)

@app.route('/wallet')
def wallet_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    wallet = Wallet.query.filter_by(user_id=user.id).first()
    
    if not wallet:
        flash('No wallet found for your account', 'error')
        return redirect(url_for('dashboard'))
    
    # Update balance from blockchain
    wallet.balance = wallet_service.get_usdt_balance(wallet.address)
    db.session.commit()
    
    # Get recent transactions
    transactions = Transaction.query.filter_by(wallet_id=wallet.id).order_by(Transaction.created_at.desc()).limit(10).all()
    
    return render_template('wallet.html', wallet=wallet, transactions=transactions)

@app.route('/wallet/send', methods=['GET', 'POST'])
def send_usdt():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    wallet = Wallet.query.filter_by(user_id=user.id).first()
    
    if not wallet:
        flash('No wallet found for your account', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        to_address = request.form.get('to_address')
        amount = request.form.get('amount')
        password = request.form.get('password')
        
        # Verify password
        if not check_password_hash(user.password_hash, password):
            flash('Invalid password', 'error')
            return redirect(url_for('send_usdt'))
        
        # Decrypt private key
        try:
            private_key = wallet_service.decrypt_private_key(wallet.encrypted_private_key)
        except Exception as e:
            flash('Error decrypting wallet', 'error')
            return redirect(url_for('send_usdt'))
        
        # Send transaction
        result = wallet_service.send_usdt(wallet.address, to_address, amount, private_key)
        
        if result['status'] == 'pending':
            # Create transaction record
            new_transaction = Transaction(
                wallet_id=wallet.id,
                tx_hash=result['tx_hash'],
                amount=amount,
                tx_type='send',
                status='pending',
                to_address=to_address
            )
            db.session.add(new_transaction)
            db.session.commit()
            
            flash('Transaction sent successfully', 'success')
            return redirect(url_for('wallet_dashboard'))
        else:
            flash(f'Error sending transaction: {result.get("error", "Unknown error")}', 'error')
            return redirect(url_for('send_usdt'))
    
    return render_template('send_usdt.html', wallet=wallet)

@app.route('/wallet/receive')
def receive_usdt():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    wallet = Wallet.query.filter_by(user_id=user.id).first()
    
    if not wallet:
        flash('No wallet found for your account', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('receive_usdt.html', wallet=wallet)

@app.route('/api/check_transaction/<tx_hash>')
def check_transaction(tx_hash):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Find the transaction
    transaction = Transaction.query.filter_by(tx_hash=tx_hash).first()
    
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    # Check if the transaction belongs to the current user
    wallet = Wallet.query.get(transaction.wallet_id)
    if wallet.user_id != session['user_id']:
        return jsonify({'error': 'Not authorized'}), 403
    
    # Check status on blockchain
    result = wallet_service.check_transaction_status(tx_hash)
    
    # Update transaction status if needed
    if result['status'] != transaction.status:
        transaction.status = result['status']
        if 'block_number' in result:
            transaction.block_number = result['block_number']
        db.session.commit()
    
    return jsonify({
        'status': transaction.status,
        'block_number': transaction.block_number
    })

@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    notifications = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).all()
    
    return render_template('notifications.html', notifications=notifications)

@app.route('/mark_notification_read/<int:notification_id>')
def mark_notification_read(notification_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    notification = Notification.query.get_or_404(notification_id)
    
    # Check if the notification belongs to the current user
    if notification.user_id != session['user_id']:
        flash('You do not have permission to view this notification', 'error')
        return redirect(url_for('notifications'))
    
    notification.is_read = True
    db.session.commit()
    
    return redirect(url_for('order_detail', order_id=notification.order_id))

@app.route('/api/notifications/unread_count')
def unread_notification_count():
    if 'user_id' not in session:
        return jsonify({'unread_count': 0})
    
    user_id = session['user_id']
    unread_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
    
    return jsonify({'unread_count': unread_count})

# Template filter for parsing duration strings
@app.template_filter('parse_duration')
def parse_duration(duration_str):
    """
    Parse duration string like '1 hour', '2 days' etc. to a timedelta
    """
    # Handle empty or None values
    if not duration_str:
        return timedelta(hours=24)  # Default to 24 hours if empty
    
    duration_str = str(duration_str).strip().lower()
    
    try:
        # Try to handle formats like "1hour" or "2days" without spaces
        if ' ' not in duration_str:
            # Extract number from the beginning of the string
            value = 0
            for i, char in enumerate(duration_str):
                if not char.isdigit():
                    if i > 0:
                        value = int(duration_str[:i])
                        unit = duration_str[i:]
                    break
            else:
                # If no letters found (just a number), default to hours
                value = int(duration_str) if duration_str.isdigit() else 1
                unit = 'hours'
        else:
            # Handle normal format like "1 hour"
            parts = duration_str.split(' ')
            if len(parts) < 2:
                return timedelta(hours=24)  # Default if malformed
                
            value = int(parts[0])
            unit = parts[1].lower()
        
        # Ensure we have a value
        if value <= 0:
            value = 1
        
        # Check unit and return timedelta
        if 'hour' in unit:
            return timedelta(hours=value)
        elif 'min' in unit:
            return timedelta(minutes=value)
        elif 'day' in unit:
            return timedelta(days=value)
        elif 'week' in unit:
            return timedelta(weeks=value)
        elif 'month' in unit:
            return timedelta(days=30 * value)  # Approximate
        else:
            return timedelta(hours=value)  # Default to hours
    except Exception:
        # If any error occurs during parsing, return a default value
            return timedelta(hours=24)  # Default to 24 hours

@app.route('/create_review/<int:user_id>', methods=['POST'])
def create_review(user_id):
    """
    Create a new review for a user
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Make sure you're not reviewing yourself
    if user_id == session['user_id']:
        flash('You cannot review yourself.')
        return redirect(url_for('profile', username=User.query.get(user_id).username))
    
    rating = request.form.get('rating')
    comment = request.form.get('comment')
    order_id = request.form.get('order_id')
    
    if not rating or not comment:
        flash('Please provide both a rating and a comment.')
        return redirect(request.referrer or url_for('profile'))
    
    new_review = Review(
        reviewer_id=session['user_id'],
        recipient_id=user_id,
        order_id=order_id if order_id else None,
        rating=int(rating),
        comment=comment
    )
    
    db.session.add(new_review)
    db.session.commit()
    
    flash('Your review has been submitted successfully.')
    return redirect(request.referrer or url_for('profile'))

@app.route('/test/parse_duration')
def test_parse_duration():
    return render_template('test_order_detail.html')

@app.route('/publish_draft/<int:post_id>', methods=['POST'])
def publish_draft(post_id):
    """
    Publish a draft post
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    post = Post.query.get_or_404(post_id)
    
    # Verify the current user owns this post
    if post.seller_id != session['user_id']:
        flash('You do not have permission to edit this post', 'error')
        return redirect(url_for('seller_dashboard'))
    
    # Verify it's a draft
    if not post.is_draft:
        flash('This post is already published', 'info')
        return redirect(url_for('seller_dashboard'))
    
    # Publish the draft
    post.is_draft = False
    db.session.commit()
    
    flash('Your draft has been published successfully!', 'success')
    return redirect(url_for('seller_dashboard'))

@app.route('/boost_post/<int:post_id>')
def boost_post(post_id):
    """
    Show boost confirmation page for an existing post
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    post = Post.query.get_or_404(post_id)
    
    # Verify the current user owns this post
    if post.seller_id != session['user_id']:
        flash('You do not have permission to boost this post', 'error')
        return redirect(url_for('seller_dashboard'))
    
    # Get user's wallet
    user = User.query.get(session['user_id'])
    wallet = Wallet.query.filter_by(user_id=user.id).first()
    
    if not wallet:
        flash('No wallet found for your account', 'error')
        return redirect(url_for('seller_dashboard'))
    
    return render_template('boost_post.html', post=post, wallet=wallet)

@app.route('/process_boost/<int:post_id>', methods=['POST'])
def process_boost(post_id):
    """
    Process the boost payment for an existing post
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    post = Post.query.get_or_404(post_id)
    
    # Verify the current user owns this post
    if post.seller_id != session['user_id']:
        flash('You do not have permission to boost this post', 'error')
        return redirect(url_for('seller_dashboard'))
    
    # Get user's wallet
    user = User.query.get(session['user_id'])
    wallet = Wallet.query.filter_by(user_id=user.id).first()
    
    if not wallet:
        flash('No wallet found for your account', 'error')
        return redirect(url_for('seller_dashboard'))
    
    # Check if user has enough balance
    if float(wallet.balance) < 10:
        flash('Insufficient funds to boost listing. You need at least 10 USDT.', 'error')
        return redirect(url_for('seller_dashboard'))
    
    # Process the boost payment
    # Set boost expiry date (7 days from now)
    post.is_boosted = True
    post.boost_expires_at = datetime.utcnow() + timedelta(days=7)
    
    # Deduct 10 USDT from wallet
    new_balance = float(wallet.balance) - 10
    wallet.balance = str(new_balance)
    
    # Create a transaction record for the boost payment
    new_transaction = Transaction(
        wallet_id=wallet.id,
        tx_hash=f"boost-{datetime.utcnow().timestamp()}-{session['user_id']}",
        amount="10",
        tx_type="boost",
        status="completed",
        to_address="PEER_PLATFORM"  # Platform wallet address would go here
    )
    
    db.session.add(new_transaction)
    db.session.commit()
    
    flash('Your listing has been boosted and will appear at the top of search results for 7 days!', 'success')
    return redirect(url_for('seller_dashboard'))

@app.route('/tutorial')
def tutorial():
    """Display the tutorial page for new users"""
    return render_template('tutorial.html')

@app.route('/kyc_verification', methods=['GET', 'POST'])
def kyc_verification():
    """Handle KYC verification requests"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        # In a real application, we would process uploaded documents here
        # For demo purposes, we're automatically approving verification
        user.is_verified = True
        user.verification_date = datetime.utcnow()
        db.session.commit()
        
        flash("Your identity has been verified! You now have a verified seller badge.", "success")
        return redirect(url_for('profile'))
    
    return render_template('kyc_verification.html', user=user)

@app.route('/reply_to_review/<int:review_id>', methods=['POST'])
def reply_to_review(review_id):
    """Allow a seller to respond to a review"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    review = Review.query.get_or_404(review_id)
    
    # Check if the current user is the review recipient
    if review.recipient_id != session['user_id']:
        flash("You can only reply to reviews about you.", "error")
        return redirect(url_for('profile'))
    
    response = request.form.get('response')
    if not response:
        flash("Response cannot be empty.", "error")
        return redirect(url_for('profile'))
    
    review.response = response
    db.session.commit()
    
    flash("Your response has been added to the review.", "success")
    return redirect(url_for('profile'))

@app.route('/api/tutorial/complete', methods=['POST'])
def complete_tutorial():
    """Mark the tutorial as completed for the current user"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
        
    user = User.query.get(session['user_id'])
    # In a real implementation, we'd store this preference in the database
    # For now we just return success
    return jsonify({'success': True})

@app.route('/update_profile', methods=['POST'])
def update_profile():
    """Update user profile information"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    # Get form data
    phone_number = request.form.get('phone_number')
    dob_str = request.form.get('dob')
    location = request.form.get('location')
    
    if not phone_number or not dob_str or not location:
        flash('All fields are required to complete your profile.', 'error')
        return redirect(url_for('profile'))
    
    # Parse date of birth
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format for date of birth.', 'error')
        return redirect(url_for('profile'))
    
    # Update user information
    user.phone_number = phone_number
    user.dob = dob
    user.location = location
    
    db.session.commit()
    
    flash('Your profile has been updated successfully!', 'success')
    return redirect(url_for('profile'))

if __name__ == '__main__':
    with app.app_context():
        # Create all database tables
        db.create_all()
        
        # Check if Post table exists but needs updating
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        
        # Update Post table
        if 'post' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('post')]
            if 'is_boosted' not in columns:
                # Add missing columns
                try:
                    db.session.execute(text('ALTER TABLE post ADD COLUMN is_boosted BOOLEAN DEFAULT 0'))
                    db.session.execute(text('ALTER TABLE post ADD COLUMN boost_expires_at DATETIME'))
                    db.session.execute(text('ALTER TABLE post ADD COLUMN is_draft BOOLEAN DEFAULT 0'))
                    db.session.commit()
                    print("Added missing columns to Post table")
                except Exception as e:
                    print(f"Error adding columns to Post table: {e}")
                    db.session.rollback()
        
        # Update User table
        if 'user' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('user')]
            if 'is_verified' not in columns:
                # Add missing columns
                try:
                    db.session.execute(text('ALTER TABLE user ADD COLUMN is_verified BOOLEAN DEFAULT 0'))
                    db.session.execute(text('ALTER TABLE user ADD COLUMN verification_date DATETIME'))
                    db.session.execute(text('ALTER TABLE user ADD COLUMN reputation_score FLOAT DEFAULT 0.0'))
                    db.session.commit()
                    print("Added missing columns to User table")
                except Exception as e:
                    print(f"Error adding columns to User table: {e}")
                    db.session.rollback()
            
            # Add profile fields if they don't exist
            try:
                missing_columns = []
                if 'phone_number' not in columns:
                    missing_columns.append('ALTER TABLE user ADD COLUMN phone_number VARCHAR(20)')
                if 'dob' not in columns:
                    missing_columns.append('ALTER TABLE user ADD COLUMN dob DATE')
                if 'location' not in columns:
                    missing_columns.append('ALTER TABLE user ADD COLUMN location VARCHAR(100)')
                
                if missing_columns:
                    for sql in missing_columns:
                        db.session.execute(text(sql))
                    db.session.commit()
                    print("Added profile completion fields to User table")
            except Exception as e:
                print(f"Error adding profile completion fields to User table: {e}")
                db.session.rollback()
                
        # Update Order table
        if 'order' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('order')]
            try:
                missing_columns = []
                if 'buyer_confirmed' not in columns:
                    missing_columns.append('ALTER TABLE "order" ADD COLUMN buyer_confirmed BOOLEAN DEFAULT 0')
                if 'seller_confirmed' not in columns:
                    missing_columns.append('ALTER TABLE "order" ADD COLUMN seller_confirmed BOOLEAN DEFAULT 0')
                
                if missing_columns:
                    for sql in missing_columns:
                        db.session.execute(text(sql))
                    db.session.commit()
                    print("Added order confirmation fields to Order table")
            except Exception as e:
                print(f"Error adding order confirmation fields to Order table: {e}")
                db.session.rollback()
    
    # Start wallet monitoring service
    start_monitoring()
    
    try:
        socketio.run(app, debug=True)
    finally:
        # Ensure wallet monitoring is stopped when app exits
        stop_monitoring() 