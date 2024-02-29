from collections import defaultdict
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.core.window import Window
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from plyer import filechooser
import threading
import time
import re

import json


def load_collectible_cards(json_file_path):
    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        # Flatten the list of cards into a single list of collectible cards
        collectible_cards = [
            card
            for set_name, cards in data.items()
            for card in cards
            if card.get("collectible")
        ]
        # Create a set of collectible card IDs for fast lookup
        collectible_card_ids = {card["cardId"] for card in collectible_cards}
        return collectible_card_ids


# Load the JSON data from the file
def load_card_data(json_file_path):
    with open(json_file_path, "r", encoding="utf-8") as f:
        return json.load(f)


json_file_path = "collectible-cards.json"
card_data = load_card_data(json_file_path)
collectible_card_ids = load_collectible_cards(json_file_path)


# Function to follow the log file and extract card offerings
def follow(logfile_path, app):
    with open(logfile_path, "r") as file:
        file.seek(0, 2)
        card_offerings = []
        card_stats = {}
        tag_changes = []

        while True:
            line = file.readline()
            if not line:
                time.sleep(0.1)
                continue

            # Capture tag changes
            tag_change_match = re.search(r"name=([^\]]+).*?tag=(\S+) value=(\S+)", line)
            if tag_change_match:
                name, tag, value = tag_change_match.groups()
                tag_change_str = f"{name} | {tag} ({value})"

                # Update the list of last 20 tag changes
                if len(tag_changes) >= 20:
                    tag_changes.pop(0)
                tag_changes.append(tag_change_str)

                # Use Clock to schedule the UI update on the main thread
                Clock.schedule_once(lambda dt: app.update_tag_changes(tag_changes), 0)

            # Extract stat changes
            stat_change_match = re.search(
                r"id=(\d+).*?tag=(COST|HEALTH|ATK) value=(\d+) DEF CHANGE", line
            )
            if stat_change_match:
                entity_id, stat_type, value = stat_change_match.groups()
                if entity_id not in card_stats:
                    card_stats[entity_id] = {}
                stat_key = {"COST": "cost", "HEALTH": "health", "ATK": "attack"}[
                    stat_type
                ]
                card_stats[entity_id][stat_key] = int(value)

            # Extract full entity details
            card_info = parse_card_info(line)
            if card_info and card_info["cardId"] in collectible_card_ids:
                entity_id = card_info["entityId"]
                if entity_id in card_stats:
                    # Apply latest stat changes before adding or updating the offering
                    card_info.update(card_stats[entity_id])

                # Update or add the card offering
                found = False
                for i, offering in enumerate(card_offerings):
                    if offering["entityId"] == entity_id:
                        card_offerings[i] = card_info
                        found = True
                        break

                if not found:
                    card_offerings.append(card_info)

                # Keep the latest two offerings and apply any stat changes
                card_offerings.sort(key=lambda x: int(x["entityId"]), reverse=True)
                card_offerings = card_offerings[:2]
                for offering in card_offerings:
                    if offering["entityId"] in card_stats:
                        offering.update(card_stats[offering["entityId"]])

                app.update_card_offerings(card_offerings)


# Function to parse card information from a log line
def parse_card_info(line):
    match = re.search(r"id=(\d+) cardId=(\S+) name=([^\]]+)", line)
    if match:
        entity_id, card_id, name = match.groups()
        name = name.strip().split("]")[0].strip()
        return {"entityId": entity_id, "cardId": card_id, "name": name}
    return None


# Kivy layout for displaying card offerings
class CardOfferingsLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.card1_label = Label(text="Waiting for card offering 1...", markup=True)
        self.card2_label = Label(text="Waiting for card offering 2...", markup=True)
        self.add_widget(self.card1_label)
        self.add_widget(self.card2_label)

        # Container for tag changes
        self.tag_changes_label = Label(
            size_hint_y=None, markup=True, halign="center", valign="middle"
        )
        self.tag_changes_label.bind(
            width=lambda *x: self.tag_changes_label.setter("text_size")(
                self.tag_changes_label, (self.tag_changes_label.width, None)
            ),
            texture_size=lambda *x: self.tag_changes_label.setter("height")(
                self.tag_changes_label, self.tag_changes_label.texture_size[1]
            ),
        )
        # Ensure the label's text is centered by updating its size_hint to allow for dynamic resizing
        self.tag_changes_label.text_size = (self.tag_changes_label.width, None)

        self.tag_changes_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.tag_changes_scroll.add_widget(self.tag_changes_label)
        self.add_widget(self.tag_changes_scroll)
        self.tag_changes_scroll.scroll_y = 0

    def update_tag_changes(self, tag_changes):
        # Format and display the last 20 tag changes
        self.tag_changes_label.text = "\n".join(tag_changes)

    # Inside CardOfferingsLayout class
    def update_card_offerings(self, offerings):
        if len(offerings) == 2:
            # Retrieve dbfIds for the offerings
            dbf_id1 = self.get_dbf_id(offerings[0]["cardId"])
            dbf_id2 = self.get_dbf_id(offerings[1]["cardId"])

            # Determine which card has the lower dbfId
            lower_dbf_card_index = 0 if dbf_id1 < dbf_id2 else 1
            # Update the labels, highlighting the one with the lower dbfId
            for i, offering in enumerate(offerings):
                name = f"{offering['name']}"
                if i == lower_dbf_card_index:
                    name = (
                        f"[b][color=00FF00]{name}[/color][/b]"  # Highlight with markup
                    )

                if i == 0:
                    self.card1_label.text = f"({offering['entityId']}) {name} ID: {offering['cardId']}, {self.get_stats(offering)}"
                else:
                    self.card2_label.text = f"({offering['entityId']}) {name} ID: {offering['cardId']}, {self.get_stats(offering)}"

    def get_dbf_id(self, card_id):
        for set_name, cards in card_data.items():
            for card in cards:
                if card["cardId"] == card_id:
                    return card["dbfId"]
        return None  # Handle case where card is not found

    def get_stats(self, offering):
        card_id = offering["cardId"]

        for set_name, cards in card_data.items():
            for card in cards:
                if card["cardId"] == card_id:
                    original_card = defaultdict(lambda: None, card)
                    stats = []
                    for stat in ["cost", "attack", "health"]:
                        original_stat = original_card[stat]
                        current_stat = offering.get(
                            stat, original_stat
                        )  # Use offering stat if available, else default to original

                        # Check if the stat has changed
                        if str(current_stat) != str(
                            original_stat
                        ):  # Convert to string to ensure consistent comparison
                            # If changed, add markup for red color
                            if current_stat > original_stat:
                                stat_with_markup = (
                                    f"[b][color=00ff00]{current_stat}[/color][/b]"
                                )
                            else:
                                stat_with_markup = (
                                    f"[b][color=ff0000]{current_stat}[/color][/b]"
                                )
                        else:
                            stat_with_markup = str(current_stat)

                        stats.append(stat_with_markup)

                    return tuple(stats)  # Return the stats as a tuple

        return None, None, None  # Return None if the card is not found


# Kivy App to run the GUI
class CardOfferingsApp(App):
    def build(self):
        self.title = "ToT Solver by Egbert"
        self.layout = CardOfferingsLayout()

        Window.size = (400, 300)

        # Open file picker popup on start
        Clock.schedule_once(lambda dt: self.open_file_picker())

        return self.layout

    def open_file_picker(self):
        filechooser.open_file(
            title="Pick a log file...",
            filters=[("Zone log file", "*.log")],
            on_selection=self.on_file_pick,
            multiple=False,
        )

    def on_file_pick(self, selection):
        if selection:
            path_to_log_file = selection[0]

            Window.always_on_top = True

            self.layout.card1_label.text = "Waiting for option 1..."
            self.layout.card2_label.text = "Waiting for option 2..."
            # Start following the log file in a new thread
            follow_thread = threading.Thread(
                target=follow, args=(path_to_log_file, self), daemon=True
            )
            follow_thread.start()

    def update_card_offerings(self, offerings):
        self.layout.update_card_offerings(offerings)

    def update_tag_changes(self, tag_changes):
        self.layout.update_tag_changes(tag_changes)


# Main execution
if __name__ == "__main__":
    card_app = CardOfferingsApp()

    # Run the Kivy application
    card_app.run()
