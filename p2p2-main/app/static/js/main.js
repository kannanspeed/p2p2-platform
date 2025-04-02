document.addEventListener('DOMContentLoaded', function() {
    // Handle post form preview and timer
    const postForm = document.getElementById('post-form');
    if (postForm) {
        const previewBtn = document.getElementById('preview-btn');
        const submitBtn = document.getElementById('submit-btn');
        const previewModal = document.getElementById('preview-modal');
        const closeModal = document.querySelector('.close-btn');
        const timerElement = document.getElementById('timer');
        const previewTitle = document.getElementById('preview-title');
        const previewType = document.getElementById('preview-type');
        const previewDescription = document.getElementById('preview-description');
        const previewPayment = document.getElementById('preview-payment');
        const previewTimeline = document.getElementById('preview-timeline');
        
        let timeLeft = 10;
        let timerId;
        
        // Show preview of post
        if (previewBtn) {
            previewBtn.addEventListener('click', function(e) {
                e.preventDefault();
                
                // Get form values
                const title = document.getElementById('title').value;
                const description = document.getElementById('description').value || 'No description provided';
                const postType = document.querySelector('input[name="post_type"]:checked').value;
                const paymentMethod = document.getElementById('payment_method').value;
                let paymentDisplay = paymentMethod;
                
                if (paymentMethod === 'other') {
                    const customPayment = document.getElementById('custom_payment').value;
                    paymentDisplay = customPayment || 'Other';
                }
                
                const timelineOptions = document.getElementById('timeline_options').value;
                
                // Update preview content
                previewTitle.textContent = title;
                previewType.textContent = postType;
                previewDescription.textContent = description;
                previewPayment.textContent = paymentDisplay;
                previewTimeline.textContent = timelineOptions;
                
                // Show modal
                previewModal.style.display = 'flex';
                
                // Start timer
                timeLeft = 10;
                timerElement.textContent = timeLeft;
                
                if (timerId) {
                    clearInterval(timerId);
                }
                
                submitBtn.disabled = true;
                
                timerId = setInterval(function() {
                    timeLeft--;
                    timerElement.textContent = timeLeft;
                    
                    if (timeLeft <= 0) {
                        clearInterval(timerId);
                        submitBtn.disabled = false;
                    }
                }, 1000);
            });
        }
        
        // Close preview modal
        if (closeModal) {
            closeModal.addEventListener('click', function() {
                previewModal.style.display = 'none';
                if (timerId) {
                    clearInterval(timerId);
                }
            });
        }
        
        // Handle payment method change
        const paymentMethodSelect = document.getElementById('payment_method');
        const customPaymentDiv = document.getElementById('custom_payment_div');
        
        if (paymentMethodSelect && customPaymentDiv) {
            paymentMethodSelect.addEventListener('change', function() {
                if (this.value === 'other') {
                    customPaymentDiv.style.display = 'block';
                } else {
                    customPaymentDiv.style.display = 'none';
                }
            });
        }
    }
    
    // Live chat functionality
    const messageForm = document.getElementById('message-form');
    const chatBox = document.querySelector('.chat-box');
    
    if (messageForm && chatBox) {
        messageForm.addEventListener('submit', function(e) {
            // Auto-scroll to bottom of chat on new message
            setTimeout(function() {
                chatBox.scrollTop = chatBox.scrollHeight;
            }, 100);
        });
        
        // Initial scroll to bottom
        chatBox.scrollTop = chatBox.scrollHeight;
    }
    
    // Mobile navigation toggle - IMPROVED
    const menuToggle = document.getElementById('menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    
    if (menuToggle && navLinks) {
        // Toggle menu when the button is clicked
        menuToggle.addEventListener('click', function() {
            navLinks.classList.toggle('show');
            
            // Change icon based on menu state
            const icon = menuToggle.querySelector('i');
            if (icon) {
                if (navLinks.classList.contains('show')) {
                    icon.className = 'fas fa-times'; // X icon when menu is open
                } else {
                    icon.className = 'fas fa-bars'; // Bars icon when menu is closed
                }
            }
        });
        
        // Close menu when a link is clicked
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', function() {
                navLinks.classList.remove('show');
                // Reset icon
                const icon = menuToggle.querySelector('i');
                if (icon) {
                    icon.className = 'fas fa-bars';
                }
            });
        });
        
        // Close menu when clicking outside
        document.addEventListener('click', function(event) {
            if (!navLinks.contains(event.target) && !menuToggle.contains(event.target) && navLinks.classList.contains('show')) {
                navLinks.classList.remove('show');
                // Reset icon
                const icon = menuToggle.querySelector('i');
                if (icon) {
                    icon.className = 'fas fa-bars';
                }
            }
        });
    }
    
    // Enhance responsiveness for layout adjustment
    function handleResize() {
        // Reapply layout adjustments on resize
        if (window.innerWidth > 768 && navLinks) {
            navLinks.classList.remove('show');
            const icon = menuToggle?.querySelector('i');
            if (icon) {
                icon.className = 'fas fa-bars';
            }
        }
        
        // Adjust floating elements performance based on screen size
        const floatingElements = document.querySelectorAll('.floating-element, .floating-element-slow, .floating-element-reverse');
        if (window.innerWidth < 768) {
            floatingElements.forEach(el => {
                el.style.animationDuration = '10s'; // Slower animations on mobile
            });
        } else {
            floatingElements.forEach(el => {
                el.style.animationDuration = ''; // Reset to default
            });
        }
    }
    
    // Initialize resize handler
    window.addEventListener('resize', handleResize);
    // Run once on page load
    handleResize();
    
    // Search functionality
    const searchForm = document.getElementById('search-form');
    
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            const searchInput = document.getElementById('search-input');
            if (!searchInput.value.trim()) {
                e.preventDefault();
            }
        });
    }
    
    // Order countdown timer
    const orderTimerElement = document.getElementById('order-timer');
    if (orderTimerElement) {
        const deadline = new Date(orderTimerElement.dataset.deadline).getTime();
        
        const timerInterval = setInterval(function() {
            const now = new Date().getTime();
            const distance = deadline - now;
            
            if (distance < 0) {
                clearInterval(timerInterval);
                orderTimerElement.textContent = "Time's up!";
                return;
            }
            
            const days = Math.floor(distance / (1000 * 60 * 60 * 24));
            const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);
            
            orderTimerElement.textContent = `${days}d ${hours}h ${minutes}m ${seconds}s`;
        }, 1000);
    }
    
    // Notification badge
    const notificationsBadge = document.getElementById('notifications-badge');
    
    // Function to update notification count
    function updateNotificationCount() {
        if (notificationsBadge) {
            fetch('/api/notifications/unread_count')
                .then(response => response.json())
                .then(data => {
                    const unreadCount = data.unread_count;
                    
                    if (unreadCount > 0) {
                        notificationsBadge.textContent = unreadCount;
                        notificationsBadge.classList.add('show');
                    } else {
                        notificationsBadge.classList.remove('show');
                    }
                })
                .catch(error => console.error('Error fetching notifications:', error));
        }
    }
    
    // Update notification count on page load
    updateNotificationCount();
    
    // Set interval to check for new notifications
    setInterval(updateNotificationCount, 30000); // Check every 30 seconds
    
    // Socket.IO for real-time notifications
    // Only initialize Socket.IO if the user is logged in (notifications badge exists)
    if (notificationsBadge) {
        // Get the user ID from the page (assuming it's available in a data attribute)
        const userId = document.body.dataset.userId;
        
        if (userId) {
            // Initialize Socket.IO connection
            const socket = io();
            
            // Join the user's notification room
            socket.emit('join_notifications', { user_id: userId });
            
            // Listen for new notifications
            socket.on('new_notification', function(data) {
                console.log('New notification received:', data);
                
                // Update the notification badge count
                updateNotificationCount();
                
                // Show a browser notification if permission is granted
                if (Notification.permission === 'granted') {
                    const notification = new Notification('PEER Marketplace', {
                        body: data.content,
                        icon: '/static/img/logo.png'
                    });
                    
                    // Open the order detail page when the notification is clicked
                    notification.onclick = function() {
                        window.open('/order/' + data.order_id, '_blank');
                    };
                }
                // Request permission if not asked yet
                else if (Notification.permission !== 'denied') {
                    Notification.requestPermission().then(function(permission) {
                        if (permission === 'granted') {
                            const notification = new Notification('PEER Marketplace', {
                                body: data.content,
                                icon: '/static/img/logo.png'
                            });
                            
                            notification.onclick = function() {
                                window.open('/order/' + data.order_id, '_blank');
                            };
                        }
                    });
                }
            });
        }
    }

    // Smooth scroll functionality
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            
            if (href !== '#' && href.startsWith('#')) {
                e.preventDefault();
                
                const targetElement = document.querySelector(href);
                if (targetElement) {
                    targetElement.scrollIntoView({
                        behavior: 'smooth'
                    });
                }
            }
        });
    });

    // Parallax scrolling effect
    window.addEventListener('scroll', function() {
        const scrollY = window.scrollY;
        
        // Parallax for background elements
        document.querySelectorAll('.parallax').forEach(element => {
            const speed = element.getAttribute('data-speed') || 0.5;
            element.style.transform = `translateY(${scrollY * speed}px)`;
        });
        
        // Fade-in elements on scroll
        document.querySelectorAll('.fade-in-section').forEach(section => {
            const sectionTop = section.getBoundingClientRect().top;
            const windowHeight = window.innerHeight;
            
            if (sectionTop < windowHeight * 0.75) {
                section.classList.add('visible');
            }
        });
    });

    // Initialize notifications
    initializeNotifications();
    
    // Flash message auto-dismiss
    const flashMessages = document.querySelectorAll('.flash-message');
    if (flashMessages.length > 0) {
        setTimeout(() => {
            flashMessages.forEach(message => {
                message.style.opacity = '0';
                setTimeout(() => {
                    message.remove();
                }, 500); // Wait for opacity transition
            });
        }, 5000); // Show for 5 seconds
    }
    
    // Copy to clipboard functionality
    const copyButtons = document.querySelectorAll('.copy-btn');
    copyButtons.forEach(button => {
        button.addEventListener('click', function() {
            const textToCopy = this.getAttribute('data-copy');
            const originalText = this.innerHTML;
            
            navigator.clipboard.writeText(textToCopy).then(() => {
                this.innerHTML = 'Copied!';
                setTimeout(() => {
                    this.innerHTML = originalText;
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy: ', err);
            });
        });
    });
    
    // Add stars dynamically for a more vibrant background
    addDynamicStars();
    
    // Add animated coins
    addFloatingCoins();
});

// Initialize WebSocket notifications
function initializeNotifications() {
    const userId = document.body.getAttribute('data-user-id');
    const notificationsBadge = document.getElementById('notifications-badge');
    
    if (userId && notificationsBadge) {
        // Initialize Socket.IO connection
        const socket = io();
        
        socket.on('connect', function() {
            socket.emit('register', { user_id: userId });
        });
        
        socket.on('notification', function(data) {
            // Update notification count
            const currentCount = parseInt(notificationsBadge.innerText) || 0;
            notificationsBadge.innerText = currentCount + 1;
            notificationsBadge.classList.add('show');
            
            // Show notification toast
            showNotificationToast(data.message);
        });
    }
}

// Show a notification toast
function showNotificationToast(message) {
    const toast = document.createElement('div');
    toast.className = 'notification-toast';
    toast.innerHTML = `
        <div class="notification-toast-content">
            <i class="fas fa-bell"></i>
            <span>${message}</span>
        </div>
        <button class="notification-toast-close">×</button>
    `;
    
    document.body.appendChild(toast);
    
    // Show toast with animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 5000);
    
    // Close button functionality
    toast.querySelector('.notification-toast-close').addEventListener('click', function() {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    });
}

// Add dynamic stars to the background
function addDynamicStars() {
    const starsContainer = document.createElement('div');
    starsContainer.className = 'dynamic-stars';
    document.body.appendChild(starsContainer);
    
    for (let i = 0; i < 50; i++) {
        const star = document.createElement('div');
        star.className = 'dynamic-star';
        
        // Random position
        star.style.left = `${Math.random() * 100}%`;
        star.style.top = `${Math.random() * 100}%`;
        
        // Random size
        const size = Math.random() * 3 + 1; // 1-4px
        star.style.width = `${size}px`;
        star.style.height = `${size}px`;
        
        // Random animation delay
        star.style.animationDelay = `${Math.random() * 5}s`;
        
        starsContainer.appendChild(star);
    }
}

// Add floating coins for decoration
function addFloatingCoins() {
    const container = document.querySelector('.container');
    if (!container) return;
    
    const coinSymbols = ['₿', 'Ξ', '₮', 'P'];
    const coinColors = [
        'linear-gradient(135deg, #F7931A, #FFAE34)',
        'linear-gradient(135deg, #627EEA, #8596EC)',
        'linear-gradient(135deg, #2775CA, #2775CA)',
        'linear-gradient(135deg, #8367C7, #64B6FF)'
    ];
    
    for (let i = 0; i < 8; i++) {
        const coinIndex = Math.floor(Math.random() * coinSymbols.length);
        const coin = document.createElement('div');
        coin.className = i % 2 === 0 ? 'floating-coin spinning-coin' : 'floating-coin spinning-coin-reverse';
        
        // Random position
        coin.style.position = 'fixed';
        coin.style.left = `${Math.random() * 100}%`;
        coin.style.top = `${Math.random() * 100}%`;
        coin.style.zIndex = '-1';
        
        // Random size
        const size = Math.random() * 30 + 20; // 20-50px
        
        coin.innerHTML = `
            <div style="width: ${size}px; height: ${size}px; background: ${coinColors[coinIndex]}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: ${size/2}px;">
                ${coinSymbols[coinIndex]}
            </div>
        `;
        
        document.body.appendChild(coin);
    }
}

// Add styles for the dynamic elements
const style = document.createElement('style');
style.textContent = `
    .notification-toast {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: rgba(20, 23, 30, 0.95);
        color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
        display: flex;
        align-items: center;
        justify-content: space-between;
        transform: translateY(100px);
        opacity: 0;
        transition: transform 0.3s, opacity 0.3s;
        z-index: 1000;
        max-width: 350px;
    }
    
    .notification-toast.show {
        transform: translateY(0);
        opacity: 1;
    }
    
    .notification-toast-content {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .notification-toast-close {
        background: none;
        border: none;
        color: white;
        font-size: 20px;
        cursor: pointer;
        padding: 0 5px;
    }
    
    .dynamic-stars {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: -2;
    }
    
    .dynamic-star {
        position: absolute;
        background-color: white;
        border-radius: 50%;
        animation: twinkle 5s ease-in-out infinite alternate;
    }
    
    .floating-coin {
        position: absolute;
        animation-duration: 10s;
    }
    
    .fade-in-section {
        opacity: 0;
        transform: translateY(30px);
        transition: opacity 1s, transform 1s;
    }
    
    .fade-in-section.visible {
        opacity: 1;
        transform: translateY(0);
    }
    
    .nav-links {
        transition: all 0.3s ease;
    }
    
    @media (max-width: 768px) {
        .nav-links {
            position: fixed;
            top: 70px;
            left: 0;
            width: 100%;
            background: rgba(10, 13, 20, 0.95);
            backdrop-filter: blur(10px);
            flex-direction: column;
            padding: 20px;
            gap: 15px;
            transform: translateY(-100%);
            opacity: 0;
            z-index: 100;
        }
        
        .nav-links.show {
            transform: translateY(0);
            opacity: 1;
        }
        
        .menu-toggle {
            display: block !important;
            background: none;
            border: none;
            color: white;
            font-size: 24px;
            cursor: pointer;
        }
    }
`;

document.head.appendChild(style); 