import os

# Create media directory
media_dir = os.path.join(os.path.dirname(__file__), 'media')
os.makedirs(media_dir, exist_ok=True)

# Create receipts subdirectory
receipts_dir = os.path.join(media_dir, 'receipts')
os.makedirs(receipts_dir, exist_ok=True)

print("Media and receipts directories created successfully!")
