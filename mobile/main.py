"""
vMix Controller Mobile - Kivy version for iOS/Android
"""

import json
import requests
import xml.etree.ElementTree as ET
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty

Window.size = (400, 800)


class Settings:
    def __init__(self):
        self.ip = "127.0.0.1"
        self.port = "8088"

    def load(self):
        try:
            with open('vmix_settings_mobile.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.ip = data.get('ip', self.ip)
                self.port = data.get('port', self.port)
        except FileNotFoundError:
            self.save()

    def save(self):
        data = {
            'ip': self.ip,
            'port': self.port,
        }
        with open('vmix_settings_mobile.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)


class vMixAPI:
    def __init__(self, ip, port):
        self.base_url = f"http://{ip}:{port}/api"
        self.timeout = 2

    def send_command(self, command, **params):
        try:
            params_str = "&".join([f"{k}={v}" for k, v in params.items()])
            url = f"{self.base_url}/?Function={command}"
            if params_str:
                url += f"&{params_str}"
            response = requests.get(url, timeout=self.timeout)
            return response.status_code == 200
        except Exception as e:
            print(f"Command error: {e}")
            return False

    def get_xml_data(self):
        try:
            url = f"{self.base_url}/"
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                return response.text
            return None
        except Exception as e:
            print(f"Connection error: {e}")
            return None

    def get_inputs(self):
        xml_data = self.get_xml_data()
        if not xml_data:
            return []

        try:
            root = ET.fromstring(xml_data)
            inputs = []
            for input_elem in root.findall('inputs/input'):
                input_data = {
                    'number': input_elem.get('number'),
                    'title': input_elem.get('title', f"Input {input_elem.get('number')}"),
                    'short_title': input_elem.get('shortTitle', '')
                }
                inputs.append(input_data)
            return inputs
        except Exception as e:
            print(f"XML parsing error: {e}")
            return []

    def get_active_input(self):
        xml_data = self.get_xml_data()
        if not xml_data:
            return None
        try:
            root = ET.fromstring(xml_data)
            active_input = root.find('active')
            return active_input.text if active_input is not None else None
        except Exception as e:
            print(f"Active input error: {e}")
            return None

    def get_preview_input(self):
        xml_data = self.get_xml_data()
        if not xml_data:
            return None
        try:
            root = ET.fromstring(xml_data)
            preview_input = root.find('preview')
            return preview_input.text if preview_input is not None else None
        except Exception as e:
            print(f"Preview input error: {e}")
            return None


class VMixControllerMobile(App):
    status_text = StringProperty("Ready to connect")
    connected = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "vMix Controller Mobile"
        self.settings = Settings()
        self.settings.load()
        self.vmix_api = None
        self.inputs = []
        self.active_input = None
        self.preview_input = None
        self.ftb_active = False

    def build(self):
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # Settings
        settings_layout = BoxLayout(orientation='vertical', size_hint_y=0.25, spacing=5)

        ip_layout = BoxLayout(size_hint_y=None, height=40, spacing=5)
        ip_layout.add_widget(Label(text="IP:", size_hint_x=0.15))
        self.ip_input = TextInput(text=self.settings.ip, multiline=False, size_hint_x=0.85)
        ip_layout.add_widget(self.ip_input)
        settings_layout.add_widget(ip_layout)

        port_layout = BoxLayout(size_hint_y=None, height=40, spacing=5)
        port_layout.add_widget(Label(text="Port:", size_hint_x=0.15))
        self.port_input = TextInput(text=self.settings.port, multiline=False, size_hint_x=0.85)
        port_layout.add_widget(self.port_input)
        settings_layout.add_widget(port_layout)

        self.connect_btn = Button(text="Connect", size_hint_y=None, height=40, background_color=(0.2, 0.6, 1, 1))
        self.connect_btn.bind(on_press=self.connect_to_vmix)
        settings_layout.add_widget(self.connect_btn)

        main_layout.add_widget(settings_layout)

        # Status
        self.status_label = Label(text=self.status_text, size_hint_y=0.08)
        self.bind(status_text=lambda *args: setattr(self.status_label, 'text', self.status_text))
        main_layout.add_widget(self.status_label)

        # Inputs
        scroll_view = ScrollView(size_hint=(1, 0.35))
        self.tiles_layout = GridLayout(cols=2, spacing=5, size_hint_y=None)
        self.tiles_layout.bind(minimum_height=self.tiles_layout.setter('height'))
        scroll_view.add_widget(self.tiles_layout)
        main_layout.add_widget(scroll_view)

        # Controls
        controls_layout = BoxLayout(orientation='vertical', size_hint_y=0.27, spacing=5)

        buttons_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)
        self.quick_play_btn = Button(text="QUICK PLAY", background_color=(0.2, 0.6, 1, 1))
        self.quick_play_btn.bind(on_press=self.quick_play)
        self.quick_play_btn.disabled = True
        buttons_layout.add_widget(self.quick_play_btn)

        self.ftb_btn = Button(text="FTB", background_color=(1, 0.2, 0.2, 1))
        self.ftb_btn.bind(on_press=self.fade_to_black)
        self.ftb_btn.disabled = True
        buttons_layout.add_widget(self.ftb_btn)

        controls_layout.add_widget(buttons_layout)

        # Info
        info_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)

        preview_layout = BoxLayout(orientation='vertical', size_hint_x=0.5)
        preview_layout.add_widget(Label(text="Preview:", size_hint_y=0.3, font_size='10sp'))
        self.preview_label = Label(text="Not selected", size_hint_y=0.7)
        preview_layout.add_widget(self.preview_label)
        info_layout.add_widget(preview_layout)

        active_layout = BoxLayout(orientation='vertical', size_hint_x=0.5)
        active_layout.add_widget(Label(text="Program:", size_hint_y=0.3, font_size='10sp'))
        self.active_label = Label(text="No data", size_hint_y=0.7)
        active_layout.add_widget(self.active_label)
        info_layout.add_widget(active_layout)

        controls_layout.add_widget(info_layout)

        # Overlay buttons
        overlay_layout = BoxLayout(size_hint_y=None, height=40, spacing=3)
        for i in range(1, 5):
            btn = Button(text=f"OVR{i}", background_color=(1, 0.6, 0.2, 1))
            btn.layer = i
            btn.bind(on_press=self.overlay_selected)
            btn.disabled = True
            overlay_layout.add_widget(btn)

        controls_layout.add_widget(overlay_layout)
        main_layout.add_widget(controls_layout)

        Clock.schedule_interval(self.update_states, 1)

        return main_layout

    def connect_to_vmix(self, instance):
        ip = self.ip_input.text
        port = self.port_input.text

        if not ip:
            self.status_text = "Enter IP address"
            return

        try:
            self.vmix_api = vMixAPI(ip, port)
            xml_data = self.vmix_api.get_xml_data()

            if xml_data:
                self.status_text = f"Connected to {ip}:{port}"
                self.connected = True
                self.connect_btn.disabled = True
                self.load_inputs()
                self.quick_play_btn.disabled = False
                self.ftb_btn.disabled = False
            else:
                self.status_text = "Failed to connect"
                self.connected = False
        except Exception as e:
            self.status_text = f"Error: {str(e)[:30]}"
            self.connected = False

    def load_inputs(self):
        if not self.vmix_api:
            return

        self.inputs = self.vmix_api.get_inputs()
        self.active_input = self.vmix_api.get_active_input()
        self.preview_input = self.vmix_api.get_preview_input()

        self.tiles_layout.clear_widgets()

        for input_data in self.inputs:
            is_active = (self.active_input == input_data['number'])
            is_preview = (self.preview_input == input_data['number'])

            if is_active:
                bg_color = (0.6, 0.1, 0.1, 1)
            elif is_preview:
                bg_color = (0.1, 0.4, 0.7, 1)
            else:
                bg_color = (0.2, 0.2, 0.2, 1)

            btn = Button(
                text=f"V{input_data['number']}\n{(input_data['short_title'] or input_data['title'])[:12]}",
                size_hint_y=None,
                height=100,
                background_color=bg_color
            )

            btn.input_number = input_data['number']
            btn.bind(on_press=self.on_input_clicked)
            self.tiles_layout.add_widget(btn)

        self.update_info_labels()

    def on_input_clicked(self, instance):
        if not self.vmix_api:
            return

        try:
            self.vmix_api.send_command("PreviewInput", Input=instance.input_number)
            self.preview_input = instance.input_number
            self.load_inputs()
            self.status_text = f"Preview: V{instance.input_number}"
        except Exception as e:
            self.status_text = f"Error: {str(e)[:30]}"

    def update_info_labels(self):
        if self.preview_input:
            self.preview_label.text = f"V{self.preview_input}"
        else:
            self.preview_label.text = "Not selected"

        if self.active_input:
            self.active_label.text = f"V{self.active_input}"
        else:
            self.active_label.text = "No data"

    def quick_play(self, instance):
        if not self.vmix_api or not self.preview_input:
            self.status_text = "Select preview first"
            return

        try:
            self.vmix_api.send_command("Fade", Input=self.preview_input)
            self.active_input = self.preview_input
            self.load_inputs()
            self.status_text = f"Transition to V{self.preview_input}"
        except Exception as e:
            self.status_text = f"Error: {str(e)[:30]}"

    def fade_to_black(self, instance):
        if not self.vmix_api:
            return

        try:
            self.ftb_active = not self.ftb_active
            self.vmix_api.send_command("FadeToBlack")
            self.status_text = f"FTB: {'ON' if self.ftb_active else 'OFF'}"
        except Exception as e:
            self.status_text = f"Error: {str(e)[:30]}"

    def overlay_selected(self, instance):
        if not self.vmix_api or not self.preview_input:
            self.status_text = "Select preview first"
            return

        try:
            self.vmix_api.send_command(f"OverlayInput{instance.layer}", Input=self.preview_input)
            self.status_text = f"Overlay on layer {instance.layer}"
        except Exception as e:
            self.status_text = f"Error: {str(e)[:30]}"

    def update_states(self, dt):
        if self.vmix_api:
            try:
                new_active = self.vmix_api.get_active_input()
                new_preview = self.vmix_api.get_preview_input()

                if new_active != self.active_input or new_preview != self.preview_input:
                    self.active_input = new_active
                    self.preview_input = new_preview
                    self.load_inputs()
            except:
                pass


if __name__ == '__main__':
    VMixControllerMobile().run()
