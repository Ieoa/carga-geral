import pymysql


# Backend puro Python, mais portavel em Windows e em containers do que mysqlclient.
pymysql.install_as_MySQLdb()
