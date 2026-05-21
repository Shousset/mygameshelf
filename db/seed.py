# MyGameShelf — Sample Data Seeder
# Run with: python -m db.seed  (from inside mygameshelf/)

from db.models import add_game, log_session, add_to_wishlist

def seed():
    print("Seeding sample data...")

    g1 = add_game("Elden Ring",          "PC",           "RPG",             2022, "Playing",   "Masterpiece so far")
    g2 = add_game("The Witcher 3",       "PC",           "RPG",             2015, "Completed", "One of the best ever")
    g3 = add_game("Hollow Knight",       "PC",           "Metroidvania",    2017, "Backlog",   "Everyone recommends it")
    g4 = add_game("Hades",               "PC",           "Roguelike",       2020, "Completed", "Addictive loop")
    g5 = add_game("Cyberpunk 2077",      "PC",           "Action RPG",      2020, "Abandoned", "Needs more time")
    g6 = add_game("Stardew Valley",      "PC",           "Simulation",      2016, "Backlog",   "Relaxing game to try")

    log_session(g1, 4.5, "Got to Margit")
    log_session(g1, 3.0, "Explored Limgrave")
    log_session(g2, 6.0, "Finished main story")
    log_session(g4, 5.5, "Unlocked new boon builds")

    add_to_wishlist("God of War Ragnarök", "PS5",  "High",   "Sequel to one of the best games ever")
    add_to_wishlist("Baldur's Gate 3",     "PC",   "High",   "RPG of the year 2023")
    add_to_wishlist("Disco Elysium",       "PC",   "Medium", "Unique narrative RPG")

    print("✅ Sample data loaded!")

if __name__ == "__main__":
    seed()
