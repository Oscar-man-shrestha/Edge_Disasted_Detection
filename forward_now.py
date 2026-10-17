from alert_store import AlertStore

sent, left = AlertStore().forward_pending()
print(f"sent {sent}, still buffered {left}")