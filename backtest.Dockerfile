#5/24/24 latest version of ubuntu
FROM ubuntu:24.04

#Software-properties-common needed to add repos.
RUN apt-get update
RUN apt-get -y install software-properties-common
RUN apt-get -y install pkg-config
RUN apt-get -y install default-libmysqlclient-dev
RUN apt-get -y install 
RUN add-apt-repository ppa:deadsnakes/ppa -y
RUN apt-get update

#Install python3.12, or at least make sure its there.
RUN apt-get -y install python3.12

#Dependencies required for cpython libraries.
RUN apt-get -y install python3.12-dev

#Install pip.
RUN apt-get -y install python3-pip

#Add user.
RUN useradd -ms /bin/bash ec2-user
USER ec2-user

#Copy code over.
COPY . /nt
WORKDIR /nt

#Install libraries.
RUN pip3 install -r backtest/requirements.txt --break-system-packages

#Start the worker.
CMD ~/.local/bin/celery -A celery_worker worker -l WARNING -c 4 -n worker1@%n -Q worker_main,worker_priority --time-limit 60