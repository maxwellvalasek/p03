import qrcode

# Your server's URL for the QR redeem page
url = "http://10.41.147.22:3000/qr-redeem"

# Generate the QR code
img = qrcode.make(url)

# Save the QR code as an image file
img.save("qr_redeem.png")

print("QR code saved as qr_redeem.png")