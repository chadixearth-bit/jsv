from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from inventory.models import InventoryItem, Brand, Category, Warehouse
from sales.models import Sale, SaleItem
from decimal import Decimal
import random
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Generate sample hardware items and sales data'

    def handle(self, *args, **options):
        # Create brands
        brands = [
            "DeWalt", "Milwaukee", "Makita", "Bosch", "Stanley",
            "Black & Decker", "Craftsman", "Ryobi", "Ridgid", "Hilti"
        ]
        brand_objects = []
        for brand_name in brands:
            brand, _ = Brand.objects.get_or_create(name=brand_name)
            brand_objects.append(brand)

        # Create categories
        categories = [
            "Power Tools", "Hand Tools", "Hardware", "Safety Equipment",
            "Electrical", "Plumbing", "Measuring Tools", "Storage", "Lighting"
        ]
        category_objects = []
        for cat_name in categories:
            category, _ = Category.objects.get_or_create(name=cat_name)
            category_objects.append(category)

        # Sample items with their categories
        items = [
            # Power Tools
            ("Cordless Drill", "Power Tools", 129.99),
            ("Circular Saw", "Power Tools", 159.99),
            ("Impact Driver", "Power Tools", 149.99),
            ("Angle Grinder", "Power Tools", 89.99),
            
            # Hand Tools
            ("Hammer", "Hand Tools", 29.99),
            ("Screwdriver Set", "Hand Tools", 39.99),
            ("Wrench Set", "Hand Tools", 49.99),
            ("Pliers Set", "Hand Tools", 34.99),
            
            # Hardware
            ("Screws (100pc)", "Hardware", 9.99),
            ("Nails (100pc)", "Hardware", 7.99),
            ("Bolts (50pc)", "Hardware", 12.99),
            ("Wall Anchors", "Hardware", 6.99),
            
            # Safety Equipment
            ("Safety Glasses", "Safety Equipment", 19.99),
            ("Work Gloves", "Safety Equipment", 24.99),
            ("Dust Mask", "Safety Equipment", 15.99),
            ("Hard Hat", "Safety Equipment", 29.99),
            
            # Electrical
            ("Wire Stripper", "Electrical", 22.99),
            ("Multimeter", "Electrical", 79.99),
            ("Electrical Tape", "Electrical", 4.99),
            ("Wire (50ft)", "Electrical", 29.99),
            
            # Plumbing
            ("Pipe Wrench", "Plumbing", 39.99),
            ("Plunger", "Plumbing", 12.99),
            ("Pipe Tape", "Plumbing", 3.99),
            ("Drain Snake", "Plumbing", 24.99),
            
            # Measuring Tools
            ("Tape Measure", "Measuring Tools", 14.99),
            ("Level", "Measuring Tools", 29.99),
            ("Laser Level", "Measuring Tools", 89.99),
            ("Caliper", "Measuring Tools", 39.99),
            
            # Storage
            ("Tool Box", "Storage", 49.99),
            ("Storage Bins", "Storage", 19.99),
            ("Tool Belt", "Storage", 34.99),
            ("Parts Organizer", "Storage", 24.99),
            
            # Lighting
            ("LED Flashlight", "Lighting", 29.99),
            ("Work Light", "Lighting", 79.99),
            ("Headlamp", "Lighting", 24.99),
            ("Light Bulbs (4pk)", "Lighting", 12.99),
        ]

        # Get or create attendant warehouse
        warehouse, _ = Warehouse.objects.get_or_create(
            name="Attendant Warehouse",
            defaults={
                'is_main': True
            }
        )

        # Create inventory items
        inventory_items = []
        for item_name, category_name, price in items:
            category = Category.objects.get(name=category_name)
            brand = random.choice(brand_objects)
            
            item, created = InventoryItem.objects.get_or_create(
                item_name=item_name,
                defaults={
                    'brand': brand,
                    'category': category,
                    'price': Decimal(str(price)),
                    'stock': random.randint(10, 50),
                    'warehouse': warehouse,
                    'model': f"{brand.name}-{random.randint(1000, 9999)}",
                    'description': f"High-quality {item_name.lower()} from {brand.name}"
                }
            )
            
            if not created:
                item.stock = random.randint(10, 50)
                item.save()
            
            inventory_items.append(item)

        # Create sample sales
        # Get or create a buyer user
        buyer, _ = User.objects.get_or_create(
            username="sample_buyer",
            defaults={
                'first_name': "Sample",
                'last_name': "Buyer",
                'email': "buyer@example.com"
            }
        )

        # Get or create an attendant user
        attendant, _ = User.objects.get_or_create(
            username="attendant",
            defaults={
                'first_name': "Store",
                'last_name': "Attendant",
                'email': "attendant@example.com"
            }
        )

        # Generate 50 sample sales
        for i in range(50):
            # Create a sale
            sale_date = datetime.now() - timedelta(days=random.randint(0, 30))
            sale = Sale.objects.create(
                buyer=buyer,
                sold_by=attendant,
                sale_date=sale_date
            )

            # Add 2-5 items to each sale
            num_items = random.randint(2, 5)
            selected_items = random.sample(inventory_items, num_items)
            
            for item in selected_items:
                quantity = random.randint(1, 3)
                SaleItem.objects.create(
                    sale=sale,
                    item=item,
                    quantity=quantity,
                    price_per_unit=item.price
                )

            # Update the total price
            sale.total_price = sum(si.total_price for si in sale.items.all())
            sale.save()

        self.stdout.write(self.style.SUCCESS('Successfully generated sample data'))
