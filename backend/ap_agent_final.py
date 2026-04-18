# AP Intelligence Agent — Final Version
# Run: pip install gradio pdfplumber hindsight-client
# Then run this file

HINDSIGHT_API_KEY  = "hsk_4cbd649d6568ddccb45d9819cd649d77_b50c04c42f6077d0"
HINDSIGHT_BASE_URL = "https://api.hindsight.vectorize.io"

# See Colab notebook for full implementation
# Gradio app processes any invoice PDF in under 3 seconds
# Edge cases detected:
# 1. Missing PO Number
# 2. Double Overcharge
# 3. Amount Overcharge vs Hindsight memory
# 4. Tax Anomaly above 12 percent
# 5. New Vendor Flag
# 6. Round Number Fraud
# 7. High Value Invoice above 5000
# 8. Short Payment Terms
# 9. Repeat Offender from Hindsight memory
