# Periodic pg_dump of the database; see backup.sh.
FROM postgres:16-alpine
RUN apk add --no-cache curl openssl
COPY backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh
ENTRYPOINT ["/usr/local/bin/backup.sh"]
