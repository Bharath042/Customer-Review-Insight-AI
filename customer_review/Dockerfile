FROM python:3.9-slim-bullseye

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for PyMySQL (and others)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/* # Clean up apt cache

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt (MUST BE BEFORE NLTK download)
RUN pip install --no-cache-dir --default-timeout=1000 --retries 5 -v \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

# --- NLP Data Download (Now that NLTK is installed) ---
# Set NLTK data environment variable
ENV NLTK_DATA /usr/local/nltk_data
# Create the directory and download NLTK data using python -c
RUN mkdir -p ${NLTK_DATA} \
    && python -c "import nltk; nltk.download('punkt', download_dir='${NLTK_DATA}')" \
    && python -c "import nltk; nltk.download('averaged_perceptron_tagger', download_dir='${NLTK_DATA}')"
    # Add any other specific NLTK datasets your app uses, e.g., 'wordnet', 'stopwords' etc.
    # Example: && python -c "import nltk; nltk.download('stopwords', download_dir='${NLTK_DATA}')"
# --- End NLP Data Download ---

# Copy the rest of the application code into the container
COPY . .

# Expose the port your Flask app runs on
EXPOSE 5000

# Command to run the application using Gunicorn (a production-grade WSGI server)
# This assumes your Flask app object is named 'app' in 'app.py'
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]