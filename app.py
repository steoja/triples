# app.py

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap5
from flask_migrate import Migrate
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from flask import jsonify
from sqlalchemy import func
import json
from flask_apscheduler import APScheduler

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a_default_secret_key')

db = SQLAlchemy(app)
migrate = Migrate(app, db)
bootstrap = Bootstrap5(app)

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

class LLC(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    properties = db.relationship('Property', backref='llc', lazy=True)

class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    llc_id = db.Column(db.Integer, db.ForeignKey('llc.id'), nullable=False)
    units = db.relationship('Unit', backref='property', lazy=True)
    expenses = db.relationship('Expense', backref='property', lazy=True)
    payables = db.relationship('Payable', backref='property', lazy=True)

class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unit_number = db.Column(db.String(20), nullable=False)
    renter_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    rent_amount = db.Column(db.Float, nullable=False)
    rent_due_date = db.Column(db.Date, nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    rent_payments = db.relationship('RentPayment', back_populates='unit', lazy=True)

class PaymentMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    method_type = db.Column(db.String(20), nullable=False)  # 'Credit Card', 'Check', or 'Cash'
    description = db.Column(db.String(100), nullable=False)
    card_number = db.Column(db.String(20), nullable=True)  # Last 4 digits for credit cards
    card_type = db.Column(db.String(20), nullable=True)  # Visa, Amex, Mastercard, etc.

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date_paid = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    vendor = db.Column(db.String(100), nullable=False)  # New field
    payment_method_type = db.Column(db.String(20), nullable=False)
    card_last_four = db.Column(db.String(4), nullable=True)
    card_type = db.Column(db.String(20), nullable=True)
    check_number = db.Column(db.String(20), nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)

EXPENSE_CATEGORIES = [
    'Utilities', 'Professional Fees', 'Landscaping', 'Cleaning',
    'Sub Contractors', 'Insurance', 'School Taxes', 'General Taxes', 'Village Taxes'
]

PAYMENT_METHOD_TYPES = ['Cash', 'Credit Card', 'Check']
CARD_TYPES = ['Visa', 'Mastercard', 'Amex', 'Discover']

class Payable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    vendor = db.Column(db.String(100), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    paid = db.Column(db.Boolean, default=False)

class RentPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_date = db.Column(db.Date, nullable=True)
    paid_amount = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Unpaid')  # 'Unpaid', 'Paid', 'Partial', 'Late'

    unit = db.relationship('Unit', back_populates='rent_payments')
    transactions = db.relationship('PaymentTransaction', back_populates='rent_payment', cascade='all, delete-orphan')

    @property
    def total_paid(self):
        return sum(transaction.amount for transaction in self.transactions)

    @property
    def balance_due(self):
        return self.amount - self.total_paid

    @property
    def is_fully_paid(self):
        return self.total_paid >= self.amount

class PaymentTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rent_payment_id = db.Column(db.Integer, db.ForeignKey('rent_payment.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # e.g., 'Cash', 'Check', 'Credit Card'
    notes = db.Column(db.Text, nullable=True)
    rent_payment = db.relationship('RentPayment', back_populates='transactions')

def create_initial_payment_methods():
    with app.app_context():
        if PaymentMethod.query.count() == 0:
            default_methods = [
                PaymentMethod(method_type='Cash', description='Cash'),
                PaymentMethod(method_type='Credit Card', description='Visa Card', card_type='Visa', card_number='1234'),
                PaymentMethod(method_type='Credit Card', description='Mastercard', card_type='Mastercard', card_number='5678'),
            ]
            db.session.bulk_save_objects(default_methods)
            db.session.commit()
            print("Initial payment methods created.")
        else:
            print("Payment methods already exist.")


@app.route('/')
def index():
    llcs = LLC.query.all()
    return render_template('index.html', llcs=llcs)

@app.route('/llc/add', methods=['GET', 'POST'])
def add_llc():
    if request.method == 'POST':
        name = request.form['name']
        new_llc = LLC(name=name)
        db.session.add(new_llc)
        db.session.commit()
        flash('LLC added successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('add_llc.html')

@app.route('/llc/<int:llc_id>')
def llc_detail(llc_id):
    llc = LLC.query.get_or_404(llc_id)
    return render_template('llc_detail.html', llc=llc)

@app.route('/property/add/<int:llc_id>', methods=['GET', 'POST'])
def add_property(llc_id):
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        new_property = Property(name=name, address=address, llc_id=llc_id)
        db.session.add(new_property)
        db.session.commit()
        flash('Property added successfully!', 'success')
        return redirect(url_for('llc_detail', llc_id=llc_id))
    return render_template('add_property.html', llc_id=llc_id)

@app.route('/property/<int:property_id>', methods=['GET', 'POST'])
def property_detail(property_id):
    property = Property.query.get_or_404(property_id)
    credit_cards = PaymentMethod.query.filter_by(method_type='Credit Card').all()
    
    if request.method == 'POST':
        if 'add_payable' in request.form:
            new_payable = Payable(
                description=request.form['description'],
                amount=float(request.form['amount']),
                due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%d').date(),
                category=request.form['category'],
                vendor=request.form['vendor'],
                property_id=property_id
            )
            db.session.add(new_payable)
            db.session.commit()
            flash('Payable added successfully!', 'success')
        elif 'add_expense' in request.form:
            new_expense = Expense(
                description=request.form['description'],
                amount=float(request.form['amount']),
                date_paid=datetime.strptime(request.form['date_paid'], '%Y-%m-%d').date(),
                category=request.form['category'],
                vendor=request.form['vendor'],
                payment_method_type=request.form['payment_method_type'],
                property_id=property_id
            )
            if new_expense.payment_method_type == 'Credit Card':
                credit_card = PaymentMethod.query.get(int(request.form['credit_card_id']))
                new_expense.card_last_four = credit_card.card_number[-4:]
                new_expense.card_type = credit_card.card_type
            elif new_expense.payment_method_type == 'Check':
                new_expense.check_number = request.form['check_number']
            
            db.session.add(new_expense)
            db.session.commit()
            flash('Expense added successfully!', 'success')
        
        return redirect(url_for('property_detail', property_id=property_id))
    
    return render_template('property_detail.html', 
                           property=property, 
                           categories=EXPENSE_CATEGORIES, 
                           payment_method_types=PAYMENT_METHOD_TYPES, 
                           credit_cards=credit_cards,)

@app.route('/unit/add/<int:property_id>', methods=['GET', 'POST'])
def add_unit(property_id):
    property = Property.query.get_or_404(property_id)
    if request.method == 'POST':
        new_unit = Unit(
            unit_number=request.form['unit_number'],
            renter_name=request.form['renter_name'],
            phone_number=request.form['phone_number'],
            email=request.form['email'],
            rent_amount=float(request.form['rent_amount']),
            rent_due_date=datetime.strptime(request.form['rent_due_date'], '%Y-%m-%d').date(),
            property_id=property_id
        )
        db.session.add(new_unit)
        db.session.commit()
        flash('Unit added successfully!', 'success')
        return redirect(url_for('property_detail', property_id=property_id))
    return render_template('add_unit.html', property=property)

@app.route('/unit/edit/<int:unit_id>', methods=['GET', 'POST'])
def edit_unit(unit_id):
    unit = Unit.query.get_or_404(unit_id)
    if request.method == 'POST':
        unit.unit_number = request.form['unit_number']
        unit.renter_name = request.form['renter_name']
        unit.phone_number = request.form['phone_number']
        unit.email = request.form['email']
        unit.rent_amount = float(request.form['rent_amount'])
        unit.rent_due_date = datetime.strptime(request.form['rent_due_date'], '%Y-%m-%d').date()
        db.session.commit()
        flash('Unit updated successfully!', 'success')
        return redirect(url_for('property_detail', property_id=unit.property_id))
    return render_template('edit_unit.html', unit=unit)

@app.route('/unit/delete/<int:unit_id>', methods=['POST'])
def delete_unit(unit_id):
    unit = Unit.query.get_or_404(unit_id)
    property_id = unit.property_id
    db.session.delete(unit)
    db.session.commit()
    flash('Unit deleted successfully!', 'success')
    return redirect(url_for('property_detail', property_id=property_id))

@app.route('/payment_methods')
def payment_methods():
    methods = PaymentMethod.query.all()
    return render_template('payment_methods.html', methods=methods)

@app.route('/payment_method/add', methods=['GET', 'POST'])
def add_payment_method():
    if request.method == 'POST':
        method_type = request.form['method_type']
        description = request.form['description']
        card_number = request.form.get('card_number')
        card_type = request.form.get('card_type')
        
        if method_type == 'Credit Card':
            card_number = card_number[-4:]  # Only store last 4 digits
        
        new_method = PaymentMethod(
            method_type=method_type,
            description=description,
            card_number=card_number,
            card_type=card_type
        )
        db.session.add(new_method)
        db.session.commit()
        flash('Payment method added successfully!', 'success')
        return redirect(url_for('payment_methods'))
    return render_template('add_payment_method.html', method_types=PAYMENT_METHOD_TYPES, card_types=CARD_TYPES)

@app.route('/expense/<int:expense_id>')
def expense_detail(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    return render_template('expense_detail.html', expense=expense)

@app.route('/expense/edit/<int:expense_id>', methods=['GET', 'POST'])
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    credit_cards = PaymentMethod.query.filter_by(method_type='Credit Card').all()

    if request.method == 'POST':
        expense.description = request.form['description']
        expense.amount = float(request.form['amount'])
        expense.date_paid = datetime.strptime(request.form['date_paid'], '%Y-%m-%d').date()
        expense.category = request.form['category']
        expense.vendor = request.form['vendor']  # Add this line
        expense.payment_method_type = request.form['payment_method_type']

        if expense.payment_method_type == 'Credit Card':
            credit_card = PaymentMethod.query.get(int(request.form['credit_card_id']))
            expense.card_last_four = credit_card.card_number
            expense.card_type = credit_card.card_type
            expense.check_number = None
        elif expense.payment_method_type == 'Check':
            expense.check_number = request.form['check_number']
            expense.card_last_four = None
            expense.card_type = None
        else:
            expense.card_last_four = None
            expense.card_type = None
            expense.check_number = None

        db.session.commit()
        flash('Expense updated successfully!', 'success')
        return redirect(url_for('property_detail', property_id=expense.property_id))

    return render_template('edit_expense.html', 
                           expense=expense, 
                           categories=EXPENSE_CATEGORIES, 
                           payment_method_types=PAYMENT_METHOD_TYPES, 
                           credit_cards=credit_cards)

@app.route('/payment_method/edit/<int:method_id>', methods=['GET', 'POST'])
def edit_payment_method(method_id):
    payment_method = PaymentMethod.query.get_or_404(method_id)
    
    if request.method == 'POST':
        payment_method.method_type = request.form['method_type']
        payment_method.description = request.form['description']
        
        if payment_method.method_type == 'Credit Card':
            payment_method.card_number = request.form['card_number'][-4:]  # Store only last 4 digits
            payment_method.card_type = request.form['card_type']
        else:
            payment_method.card_number = None
            payment_method.card_type = None
        
        db.session.commit()
        flash('Payment method updated successfully!', 'success')
        return redirect(url_for('payment_methods'))
    
    return render_template('edit_payment_method.html', 
                           payment_method=payment_method, 
                           method_types=PAYMENT_METHOD_TYPES, 
                           card_types=CARD_TYPES)

@app.route('/payment_method/delete/<int:method_id>', methods=['POST'])
def delete_payment_method(method_id):
    payment_method = PaymentMethod.query.get_or_404(method_id)
    
    if payment_method.method_type != 'Credit Card':
        flash('Only credit card payment methods can be deleted.', 'error')
    else:
        db.session.delete(payment_method)
        db.session.commit()
        flash('Credit card deleted successfully.', 'success')
    
    return redirect(url_for('payment_methods'))

@app.route('/vendor-suggestions')
def vendor_suggestions():
    query = request.args.get('query', '').lower()
    
    # Query distinct vendors that match the input (case-insensitive)
    vendors = db.session.query(Expense.vendor)\
        .filter(func.lower(Expense.vendor).like(f"%{query}%"))\
        .distinct()\
        .order_by(Expense.vendor)\
        .limit(10)\
        .all()
    
    # Extract vendor names from the query result
    suggestions = [vendor[0] for vendor in vendors]
    
    return jsonify(suggestions)

@app.route('/payable/<int:payable_id>/mark-as-paid', methods=['POST'])
def mark_payable_as_paid(payable_id):
    payable = Payable.query.get_or_404(payable_id)
    
    new_expense = Expense(
        description=payable.description,
        amount=payable.amount,
        date_paid=datetime.strptime(request.form['date_paid'], '%Y-%m-%d').date(),
        category=payable.category,
        vendor=payable.vendor,
        payment_method_type=request.form['payment_method_type'],
        property_id=payable.property_id
    )

    if new_expense.payment_method_type == 'Credit Card':
        credit_card = PaymentMethod.query.get(int(request.form['credit_card_id']))
        new_expense.card_last_four = credit_card.card_number[-4:]
        new_expense.card_type = credit_card.card_type
    elif new_expense.payment_method_type == 'Check':
        new_expense.check_number = request.form['check_number']

    db.session.add(new_expense)
    db.session.delete(payable)
    db.session.commit()

    flash('Payable marked as paid and converted to an expense.', 'success')
    return redirect(url_for('property_detail', property_id=payable.property_id))

@app.route('/unit/<int:unit_id>/rent_payments', methods=['GET', 'POST'])
def unit_rent_payments(unit_id):
    unit = Unit.query.get_or_404(unit_id)
    
    if request.method == 'POST':
        rent_payment_id = request.form.get('rent_payment_id')
        amount = float(request.form.get('amount'))
        payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
        payment_method = request.form.get('payment_method')
        notes = request.form.get('notes')
        
        rent_payment = RentPayment.query.get(rent_payment_id)
        
        # Calculate late fee
        late_fee = calculate_late_fee(rent_payment.due_date, payment_date, rent_payment.amount)
        
        new_transaction = PaymentTransaction(
            rent_payment_id=rent_payment_id,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            notes=notes
        )
        db.session.add(new_transaction)
        
        # If there's a late fee, add it as a separate transaction
        if late_fee > 0:
            late_fee_transaction = PaymentTransaction(
                rent_payment_id=rent_payment_id,
                amount=late_fee,
                payment_date=payment_date,
                payment_method='Late Fee',
                notes=f'Late fee for {late_fee} days'
            )
            db.session.add(late_fee_transaction)
        
        # Update rent payment status
        if rent_payment.is_fully_paid:
            rent_payment.status = 'Paid'
        elif rent_payment.total_paid > 0:
            rent_payment.status = 'Partial'
        
        if payment_date > rent_payment.due_date:
            rent_payment.status = 'Late'
        
        db.session.commit()
        flash('Payment transaction recorded successfully.', 'success')
        return redirect(url_for('unit_rent_payments', unit_id=unit_id))
    
    rent_payments = RentPayment.query.filter_by(unit_id=unit_id).order_by(RentPayment.due_date.desc()).all()
    return render_template('unit_rent_payments.html', unit=unit, rent_payments=rent_payments)

@app.route('/generate_rent_payments/<int:property_id>')
def generate_rent_payments(property_id):
    property = Property.query.get_or_404(property_id)
    current_date = datetime.now().date()
    
    for unit in property.units:
        # Check if a rent payment already exists for the current month
        existing_payment = RentPayment.query.filter(
            RentPayment.unit_id == unit.id,
            func.extract('year', RentPayment.due_date) == current_date.year,
            func.extract('month', RentPayment.due_date) == current_date.month
        ).first()
        
        if not existing_payment:
            # Create a new rent payment for the current month
            new_payment = RentPayment(
                unit_id=unit.id,
                due_date=datetime(current_date.year, current_date.month, unit.rent_due_date.day).date(),
                amount=unit.rent_amount,
                status='Unpaid'
            )
            db.session.add(new_payment)
    
    db.session.commit()
    flash('Rent payments generated successfully.', 'success')
    return redirect(url_for('property_detail', property_id=property_id))

def calculate_late_fee(due_date, payment_date, rent_amount):
    if payment_date <= due_date:
        return 0
    
    days_late = (payment_date - due_date).days
    if days_late <= 5:
        return 0
    
    late_fee = min((days_late - 5) * 5, 50)  # $5 per day, max $50
    return late_fee


def generate_invoices_for_all_properties():
    current_date = datetime.now().date()
    five_days_from_now = current_date + timedelta(days=5)
    
    # Get all properties
    properties = Property.query.all()
    
    for property in properties:
        for unit in property.units:
            # Check if an invoice already exists for the next month
            next_month = current_date.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1)
            
            existing_invoice = RentPayment.query.filter(
                RentPayment.unit_id == unit.id,
                func.extract('year', RentPayment.due_date) == next_month.year,
                func.extract('month', RentPayment.due_date) == next_month.month
            ).first()
            
            if not existing_invoice:
                # Calculate the due date for the next month
                next_due_date = next_month.replace(day=unit.rent_due_date.day)
                
                # Only generate the invoice if it's 5 days or less before the due date
                if next_due_date - timedelta(days=5) <= five_days_from_now:
                    new_invoice = RentPayment(
                        unit_id=unit.id,
                        due_date=next_due_date,
                        amount=unit.rent_amount,
                        status='Unpaid'
                    )
                    db.session.add(new_invoice)
    
    db.session.commit()
    print(f"Invoices generated on {current_date}")

@scheduler.task('cron', id='generate_invoices', hour=0, minute=0)
def scheduled_invoice_generation():
    with app.app_context():
        generate_invoices_for_all_properties()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_initial_payment_methods()
    app.run(host='0.0.0.0', debug=True)