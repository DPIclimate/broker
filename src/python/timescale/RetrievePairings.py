import timescale.Timescale as ts

if __name__ == "__main__":
  for row in ts.query_all_pairings():
    print(row)

  print(f"Number of entries: {ts.query_num_entries(table='id_pairings')}")
