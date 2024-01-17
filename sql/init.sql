CREATE USER 'minmatar'@'%' IDENTIFIED BY 'example';
CREATE DATABASE tools CHARACTER SET utf8mb4;
GRANT ALL PRIVILEGES ON minmatar.* TO 'minmatar'@'%';