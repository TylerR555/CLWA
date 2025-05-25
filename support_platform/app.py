from flask import Flask, render_template, g, request, redirect, url_for, flash, session
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your secret key' # Replace with a real secret key
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB max upload size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

ISSUE_TYPES = [
    "Technical Issue",
    "Billing Inquiry",
    "Feature Request",
    "Password Reset",
    "General Question"
]

TICKET_STATUSES = {
    "OPEN": "Open",
    "IN_PROGRESS": "In Progress",
    "RESOLVED": "Resolved",
    "CLOSED": "Closed"
}

class User:
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

    def __repr__(self):
        return f'<User {self.username}>'

class Ticket:
    def __init__(self, user_id, issue_type, message, screenshots=None):
        self.ticket_id = len(tickets) + 1 # Simple auto-incrementing ID
        self.user_id = user_id
        self.issue_type = issue_type
        self.message = message
        self.screenshots = screenshots if screenshots else [] # List of screenshot filenames
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.status = TICKET_STATUSES["OPEN"]
        self.replies = [] # List of reply dictionaries/objects

    def __repr__(self):
        return f'<Ticket {self.ticket_id} - {self.issue_type}>'

    def add_reply(self, user_id, text, is_support_reply=False):
        reply = {
            "user_id": user_id,
            "text": text,
            "timestamp": datetime.utcnow(),
            "is_support_reply": is_support_reply # Differentiate user vs support replies
        }
        self.replies.append(reply)
        self.updated_at = datetime.utcnow()

    def resolve(self):
        self.status = TICKET_STATUSES["RESOLVED"]
        self.updated_at = datetime.utcnow()

    def close(self):
        self.status = TICKET_STATUSES["CLOSED"]
        self.updated_at = datetime.utcnow()

tickets = [] # This will store all ticket objects

users = [User(id=1, username='testuser', password='password123')]
user_lookup = {user.username: user for user in users}

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        # In a real app, you'd query the database here
        g.user = next((user for user in users if user.id == user_id), None)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user: # If user is already logged in, redirect to home
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = user_lookup.get(username)
        if user and user.password == password: # In a real app, hash passwords!
            session.clear()
            session['user_id'] = user.id
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('index'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    g.user = None # Ensure g.user is cleared immediately
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/create_ticket', methods=['GET', 'POST'])
def create_ticket():
    if not g.user:
        flash('You must be logged in to create a ticket.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        issue_type = request.form['issue_type']
        message = request.form['message']
        
        if not issue_type or not message:
            flash('Issue type and message are required.', 'danger')
            return render_template('create_ticket.html', issue_types=ISSUE_TYPES)

        screenshot_filenames = []
        uploaded_files = request.files.getlist('screenshots')
        for file in uploaded_files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Ensure unique filenames to prevent overwrites
                base, ext = os.path.splitext(filename)
                counter = 1
                unique_filename = filename
                while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)):
                    unique_filename = f"{base}_{counter}{ext}"
                    counter += 1
                
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                screenshot_filenames.append(unique_filename)
            elif file and not allowed_file(file.filename):
                flash(f"File type not allowed for {file.filename}. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}", "warning")

        new_ticket = Ticket(
            user_id=g.user.id,
            issue_type=issue_type,
            message=message,
            screenshots=screenshot_filenames
        )
        tickets.append(new_ticket)
        flash('Ticket created successfully!', 'success')
        # Redirect to ticket detail page (to be created)
        return redirect(url_for('ticket_detail', ticket_id=new_ticket.ticket_id)) 

    return render_template('create_ticket.html', issue_types=ISSUE_TYPES)

@app.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
def ticket_detail(ticket_id):
    if not g.user:
        flash('You must be logged in to view tickets.', 'warning')
        return redirect(url_for('login'))

    # In a real app with a database, you'd query by ticket_id and also check user_id for ownership or agent permissions.
    # For now, we assume g.user is the ticket owner or an agent.
    # Simple check for user ownership:
    ticket = next((t for t in tickets if t.ticket_id == ticket_id and t.user_id == g.user.id), None)
    
    # If not owner, a support agent might be able to view any ticket - this logic is not implemented here yet.
    # For now, only owners can view.

    if not ticket:
        flash("Ticket not found or you don't have permission to view it.", "danger")
        return redirect(url_for('tickets_list'))

    if request.method == 'POST':
        if 'submit_reply' in request.form:
            reply_text = request.form['reply_text']
            if reply_text:
                # Assuming g.user is the one replying.
                # For now, all replies are from the logged-in user and not marked as 'support_reply'.
                # is_support_reply could be True if g.user.is_support_agent (a hypothetical attribute)
                ticket.add_reply(user_id=g.user.id, text=reply_text, is_support_reply=False)
                flash('Your reply has been added.', 'success')
                return redirect(url_for('ticket_detail', ticket_id=ticket.ticket_id)) # PRG pattern
            else:
                flash('Reply text cannot be empty.', 'warning')
                # No redirect here, just re-render the page with the warning
        
        elif 'resolve_ticket' in request.form:
            # Check if the user is authorized to resolve (e.g., ticket owner or admin)
            # For now, only the ticket owner (g.user) can resolve their own ticket.
            if g.user and g.user.id == ticket.user_id:
                if ticket.status != TICKET_STATUSES["RESOLVED"] and ticket.status != TICKET_STATUSES["CLOSED"]:
                    ticket.resolve() # This method is defined in the Ticket class
                    flash('Ticket has been marked as Resolved.', 'success')
                else:
                    flash('Ticket is already resolved or closed.', 'info')
            else:
                # This case should ideally not happen if button is only shown to owner, but good for safety
                flash('You are not authorized to resolve this ticket.', 'danger')
            return redirect(url_for('ticket_detail', ticket_id=ticket.ticket_id))

    # Pass TICKET_STATUSES to the template context
    return render_template('ticket_detail.html', ticket=ticket, TICKET_STATUSES=TICKET_STATUSES)

@app.route('/tickets')
def tickets_list(): # Renamed from 'tickets' to avoid conflict with the global 'tickets' list
    if not g.user:
        flash('You must be logged in to view your tickets.', 'warning')
        return redirect(url_for('login'))
    
    user_tickets = [t for t in tickets if t.user_id == g.user.id]
    user_tickets.sort(key=lambda t: t.created_at, reverse=True) # Show newest first
    
    return render_template('tickets.html', tickets=user_tickets)

@app.route('/invoice/<int:ticket_id>')
def invoice_placeholder(ticket_id):
    if not g.user:
        flash('You must be logged in to view invoices.', 'warning')
        return redirect(url_for('login'))

    # Find the ticket - for now, only the owner can see this placeholder
    ticket = next((t for t in tickets if t.ticket_id == ticket_id and t.user_id == g.user.id), None)
    
    if not ticket:
        flash("Ticket not found or you don't have permission to view its invoice.", "danger")
        return redirect(url_for('tickets_list'))

    # For now, any user who owns the ticket can see this placeholder.
    # In a real system, you might have more specific logic for who can see/generate invoices.
    return render_template('invoice_placeholder.html', ticket=ticket)

if __name__ == '__main__':
    app.run(debug=True)
