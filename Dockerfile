# Use official Playwright Python image
FROM mcr.microsoft.com/playwright/python:latest

# Set working directory
WORKDIR /app

# Copy repo files
COPY . /app

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Install Playwright browsers with dependencies
RUN playwright install --with-deps

# Expose default Flask port
EXPOSE 5000

# Headless environment
ENV PLAYWRIGHT_HEADLESS=1

# Run Flask app (Railway dynamically assigns PORT)
CMD ["python", "app.py"]
