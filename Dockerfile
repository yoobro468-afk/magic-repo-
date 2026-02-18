FROM silentdemonsd/wzmlx:hk

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

# Git install
RUN apt update && apt install -y git

COPY requirements.txt .
RUN pip install --upgrade setuptools
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "start.sh"]
