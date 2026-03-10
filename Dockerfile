# Używamy najnowszego stabilnego runtime NVIDIA
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalacja Python 3.12 i niezbędnych narzędzi
RUN apt-get update && apt-get install -y \
    software-properties-common \
    git curl build-essential wget \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.12 python3.12-dev python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

# --- KLUCZOWA POPRAWKA: Instalacja CuDNN 9.x dla CUDA 12 ---
RUN wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb \
    && dpkg -i cuda-keyring_1.1-1_all.deb \
    && apt-get update \
    && apt-get install -y libcudnn9-cuda-12 libcudnn9-dev-cuda-12 \
    && rm -rf /var/lib/apt/lists/*

# Instalacja nowoczesnego pip
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12

WORKDIR /app

# Krok 1: Instalacja zależności
COPY requirements.txt .
RUN pip3.12 install --no-cache-dir -r requirements.txt

# Krok 2: Precyzyjna instalacja PyTorch i TensorFlow pod CUDA 12.4
RUN pip3.12 install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Instalacja TensorFlow ze wsparciem GPU (and-cuda instaluje potrzebne liby wewnątrz pip)
RUN pip3.12 install --no-cache-dir "tensorflow[and-cuda]>=2.17.0"

# Krok 3: Pozostałe ML
RUN pip3.12 install --no-cache-dir cupy-cuda12x xgboost lightgbm

# Kopiowanie reszty aplikacji
COPY . .

CMD ["python3.12", "main.py"]