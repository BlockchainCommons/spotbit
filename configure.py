import server

# This script is run by the install script when spotbit is being set up.
# It allows for spotbit to function as a systemd service on a user's system.
# Once the database has been opened, spotbit can easily be run in the background.
server.configure_db()
print("database configured in /home/spotbit/.spotbit/sb.db")