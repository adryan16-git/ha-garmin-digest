ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip

RUN pip install --break-system-packages anthropic requests

COPY run.sh /run.sh
RUN chmod +x /run.sh

COPY garmin_digest/ /garmin_digest/

CMD ["/run.sh"]
