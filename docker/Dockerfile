FROM python:3


## Add deploy keys
RUN mkdir /root/.ssh/
ADD deploy_keys/robofit_arcor2_kinali_deploy /
ADD deploy_keys/robofit_arcor2_deploy /
ADD ssh_config /
RUN chmod 600 /robofit_arcor2_deploy \
	&& chmod 600 /robofit_arcor2_kinali_deploy \
    && echo "StrictHostKeyChecking no" >> /etc/ssh/ssh_config \
    && cat /ssh_config >> /etc/ssh/ssh_config

RUN cd ~ \
	&& git clone git@arcor2.github.com:robofit/arcor2.git \
	&& git clone git@arcor2_kinali.github.com:robofit/arcor2_kinali.git

RUN cd ~/arcor2 \
	&& pip install -e .
RUN cd ~/arcor2_kinali/arcor2_kinali \
	&& pip install -e .
RUN cd ~/arcor2_kinali/swagger_client \
	&& pip install -e .

RUN mkdir -p ~/project
ENV PYTHONPATH ~
ENV ARCOR2_PROJECT_PATH ~/project

expose 6789