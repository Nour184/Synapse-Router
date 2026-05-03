FROM nvidia/cuda:12.2.2-devel-ubuntu22.04

# Set the terminal to non interactive
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
	python3.10 \
	python3-pip \
	python3.10-dev \
	git \
	&& rm -rf /var/lib/apt/list/*

# Link python and pip 3 terminal commands to just python and pip
RUN ln -s /usr/bin/python3.10 /usr/bin/python
RUN ln -s /usr/bin/pip3 /usr/bin/pip

WORKDIR /WorkerNode

COPY required_libraries.txt .

# Force pip to compile .cpp with cMake and set the CUDA macro in cmake to 1
# This makes cMake compile the model to NVidia GPUs
ENV CMAKE_ARGS="-DGGML_CUDA=on"
ENV FORCE_CMAKE=1

RUN pip install --no-cache-dir -r required_libraries.txt

COPY . .

RUN chmod +x *.sh

RUN ./download_model.sh

CMD ["uvicorn", "node:app", "--host", "0.0.0.0", "--port", "5000"]
