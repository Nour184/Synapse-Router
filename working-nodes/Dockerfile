FROM nvidia/cuda:12.2.2-devel-ubuntu22.04

# Set the terminal to non interactive
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
	python3.10 \
	python3-pip \
	python3.10-dev \
	git \
	ninja-build \
	&& rm -rf /var/lib/apt/lists/*

# Link python and pip 3 terminal commands to just python and pip
RUN ln -sf /usr/bin/pip3 /usr/bin/pip
RUN ln -sf /usr/bin/python3.10 /usr/bin/python

WORKDIR /WorkerNode

COPY required_libraries.txt .

# Force pip to compile .cpp with cMake and set the CUDA macro in cmake to 1
# This makes cMake compile the model to NVidia GPUs
ENV CMAKE_ARGS="-DGGML_CUDA=on"
ENV FORCE_CMAKE=1

RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --default-timeout=1000 --no-cache-dir -r required_libraries.txt

ARG HF_TOKEN
ENV HF_TOKEN=$HF_TOKEN

COPY . .

RUN chmod +x *.sh

# RUN ./download_model.sh # ENABLE IF YOU DON't have the model in ./models

CMD ["uvicorn", "node:app", "--host", "0.0.0.0", "--port", "5000"]
