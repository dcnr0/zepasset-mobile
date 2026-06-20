import os
import json
import uuid
import io
import time
import threading
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from PIL import Image, ImageDraw, ImageFont
import requests

CONFIG_FILE = "zepasset_session.json"

class ZepAssetMobileApp(toga.App):
    def startup(self):
        # Operational State Properties
        self.image_bytes = None
        self.tag_img_bytes = None
        self.tag_mode = "text"
        self.tag_text = "SAMPLE TAG"
        self.tag_color = "#ff3333"
        
        # Interactive Layout Scale Defaults (Mapped from desktop proportions)
        self.fx_x = 40
        self.fx_y = 70
        self.fx_w = 100
        self.fx_h = 30
        
        # --- UI Assembly ---
        self.main_box = toga.Box(style=Pack(direction=COLUMN, padding=12, background_color="#140507"))
        
        # Header Status
        self.title_label = toga.Label(
            "ZEPASSET V1 - MOBILE",
            style=Pack(padding=(0, 6), text_align="center", color="#ff3333", font_weight="bold", font_size=15)
        )
        self.main_box.add(self.title_label)
        
        # Configuration Inputs
        self.api_key_entry = toga.PasswordInput(placeholder="ROBLOX API KEY", style=Pack(padding=3))
        self.target_id_entry = toga.TextInput(placeholder="TARGET USER OR GROUP ID", style=Pack(padding=3))
        self.main_box.add(self.api_key_entry)
        self.main_box.add(self.target_id_entry)
        
        # Target Parameter Filters
        self.target_type_select = toga.Selection(items=["user", "group"], style=Pack(padding=3))
        self.dim_select = toga.Selection(items=["vertical", "horizontal"], style=Pack(padding=3))
        self.main_box.add(self.target_type_select)
        self.main_box.add(self.dim_select)
        
        # Inline Content Configurator Block
        self.mode_select = toga.Selection(items=["text", "image"], on_change=self.toggle_mode, style=Pack(padding=3))
        self.txt_ent = toga.TextInput(value=self.tag_text, placeholder="Overlay Text String", on_change=self.update_text_vars, style=Pack(padding=3))
        self.color_ent = toga.TextInput(value=self.tag_color, placeholder="Hex Color Code (#ff3333)", on_change=self.update_text_vars, style=Pack(padding=3))
        
        self.main_box.add(self.mode_select)
        self.main_box.add(self.txt_ent)
        self.main_box.add(self.color_ent)
        
        # File Stream Triggers
        self.file_box = toga.Box(style=Pack(direction=ROW, padding=4))
        self.file_btn = toga.Button("Browse Source File...", on_press=self.browse_file, style=Pack(flex=1, padding=2))
        self.paste_btn = toga.Button("Paste Matrix Image", on_press=self.paste_image, style=Pack(flex=1, padding=2))
        self.file_box.add(self.file_btn)
        self.file_box.add(self.paste_btn)
        self.main_box.add(self.file_box)
        
        # Nudge & Scale Adjuster Matrix Layout
        adjust_box = toga.Box(style=Pack(direction=ROW, padding=4))
        self.btn_up = toga.Button("↑", on_press=lambda w: self.manual_adjust(0, -3, 0, 0), style=Pack(flex=1))
        self.btn_down = toga.Button("↓", on_press=lambda w: self.manual_adjust(0, 3, 0, 0), style=Pack(flex=1))
        self.btn_left = toga.Button("←", on_press=lambda w: self.manual_adjust(-3, 0, 0, 0), style=Pack(flex=1))
        self.btn_right = toga.Button("→", on_press=lambda w: self.manual_adjust(3, 0, 0, 0), style=Pack(flex=1))
        adjust_box.add(self.btn_up)
        adjust_box.add(self.btn_down)
        adjust_box.add(self.btn_left)
        adjust_box.add(self.btn_right)
        self.main_box.add(adjust_box)
        
        scale_box = toga.Box(style=Pack(direction=ROW, padding=2))
        self.btn_sz_plus = toga.Button("Scale+", on_press=lambda w: self.manual_adjust(0, 0, 6, 4), style=Pack(flex=1))
        self.btn_sz_minus = toga.Button("Scale-", on_press=lambda w: self.manual_adjust(0, 0, -6, -4), style=Pack(flex=1))
        scale_box.add(self.btn_sz_plus)
        scale_box.add(self.btn_sz_minus)
        self.main_box.add(scale_box)

        # Core Pipeline Triggers
        self.upload_btn = toga.Button("GENERATE & UPLOAD", on_press=self.start_upload, style=Pack(padding=(12, 4)))
        self.main_box.add(self.upload_btn)
        
        self.status_label = toga.Label("System Sandboxed Ready.", style=Pack(color="#00ff66", text_align="center", font_size=9))
        self.main_box.add(self.status_label)
        
        self.load_session()
        
        self.main_window = toga.MainWindow(title=self.name)
        self.main_window.content = self.main_box
        self.main_window.show()

    def toggle_mode(self, widget):
        self.tag_mode = self.mode_select.value
        if self.tag_mode == "image":
            self.txt_ent.enabled = False
            self.color_ent.enabled = False
            # Prompt for immediate overlay asset load over interface thread
            self.load_overlay_img()
        else:
            self.txt_ent.enabled = True
            self.color_ent.enabled = True

    def update_text_vars(self, widget):
        self.tag_text = self.txt_ent.value
        self.tag_color = self.color_ent.value

    def manual_adjust(self, dx, dy, dw, dh):
        self.fx_x += dx
        self.fx_y += dy
        self.fx_w = max(15, self.fx_w + dw)
        self.fx_h = max(8, self.fx_h + dh)
        self.status_label.text = f"Offset Updated: Pos({self.fx_x},{self.fx_y}) Size({self.fx_w}x{self.fx_h})"

    async def browse_file(self, widget):
        try:
            file_path = await self.main_window.open_file_dialog("Select Texture Source Background", multiple_select=False)
            if file_path is not None:
                with open(str(file_path), "rb") as f:
                    self.image_bytes = f.read()
                self.status_label.text = "Source background layer structured successfully."
        except Exception as e:
            self.status_label.text = f"File selection tracking drop: {str(e)}"

    async def load_overlay_img(self):
        try:
            file_path = await self.main_window.open_file_dialog("Select PNG Overlay Graphic", multiple_select=False)
            if file_path is not None:
                with open(str(file_path), "rb") as f:
                    self.tag_img_bytes = f.read()
                self.status_label.text = "Custom transparent overlay bytes assigned."
        except Exception as e:
            self.status_label.text = f"Overlay payload reading fault: {str(e)}"

    def paste_image(self, widget):
        # Native mobile sandbox hook notification fallback
        self.status_label.text = "Use system photo framework sheet to select files on iOS platforms."

    def start_upload(self, widget):
        api_key = self.api_key_entry.value.strip()
        target_id = self.target_id_entry.value.strip()
        target_type = self.target_type_select.value
        mode = self.dim_select.value

        if not api_key or not target_id:
            self.status_label.text = "All configuration fields are required!"
            return
        if not self.image_bytes:
            self.status_label.text = "Load a structural source file asset first!"
            return

        self.status_label.text = "Processing canvas transforms..."
        
        # Save session params inside local thread loop cleanly
        self.save_session(api_key, target_id)
        
        threading.Thread(target=self.process_and_upload, args=(api_key, target_id, target_type, mode), daemon=True).start()

    def process_and_upload(self, api_key, target_id, target_type, mode):
        render_w, render_h = 1080, 1080
        try:
            scale_factor = render_w / 180.0
            out_x = int(self.fx_x * scale_factor)
            out_y = int(self.fx_y * scale_factor)
            out_w = int(self.fx_w * scale_factor)
            out_h = int(self.fx_h * scale_factor)

            base_img = Image.open(io.BytesIO(self.image_bytes)).convert("RGBA")
            base_img = base_img.resize((render_w, render_h), Image.Resampling.LANCZOS)
            
            overlay_layer = Image.new("RGBA", (render_w, render_h), (0,0,0,0))
            
            if self.tag_mode == "text" and self.tag_text:
                font = ImageFont.load_default()
                text_element = Image.new("RGBA", (max(1, out_w), max(1, out_h)), (0,0,0,0))
                ImageDraw.Draw(text_element).text((4, 4), self.tag_text, fill=self.tag_color, font=font)
                overlay_layer.paste(text_element, (out_x, out_y), text_element)
            elif self.tag_mode == "image" and self.tag_img_bytes:
                o_im = Image.open(io.BytesIO(self.tag_img_bytes)).convert("RGBA")
                o_im = o_im.resize((max(1, out_w), max(1, out_h)), Image.Resampling.LANCZOS)
                overlay_layer.paste(o_im, (out_x, out_y), o_im)

            high_res_composite = Image.alpha_composite(base_img, overlay_layer)
            
            target_w, target_h = (100, 1024) if mode == "vertical" else (1024, 100)
            final_scaled = high_res_composite.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
            # Simulated Grid Generation Mask Mapping Sequence
            checker_img = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
            pixels = checker_img.load()
            for y in range(target_h):
                for x in range(target_w):
                    if (x + y) % 2 == 0:
                        pixels[x, y] = (0, 0, 0, 255)
            
            final_img = Image.alpha_composite(final_scaled, checker_img)
            
            img_byte_arr = io.BytesIO()
            final_img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
        except Exception as e:
            self.show_status_main(f"Matrix Processing Exception: {str(e)}")
            return

        creator_config = {"groupId": target_id} if target_type == "group" else {"userId": target_id}
        asset_request = {
            "assetType": "Decal",
            "displayName": str(uuid.uuid4()),
            "description": "/ ZEPASSET MOBILE PRO /",
            "creationContext": {"creator": creator_config}
        }

        files = {
            'request': (None, json.dumps(asset_request), 'application/json'),
            'fileContent': (f'matrix_{target_w}x{target_h}.png', img_byte_arr, 'image/png')
        }
        headers = {'x-api-key': api_key}

        try:
            response = requests.post('https://apis.roblox.com/assets/v1/assets', headers=headers, files=files)
            if response.status_code in [200, 201]:
                self.show_status_main("Image file successfully deployed onto production endpoints!")
            else:
                self.show_status_main(f"Pipeline Error {response.status_code}: {response.text}")
        except Exception as e:
            self.show_status_main(f"Network Layer Exception drop: {str(e)}")

    def show_status_main(self, message):
        self.status_label.text = message

    def save_session(self, api_key, target_id):
        try:
            path = os.path.join(self.paths.app, CONFIG_FILE)
            with open(path, "w") as f:
                json.dump({"api_key": api_key, "target_id": target_id}, f)
        except: pass

    def load_session(self):
        try:
            path = os.path.join(self.paths.app, CONFIG_FILE)
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
                    self.api_key_entry.value = data.get("api_key", "")
                    self.target_id_entry.value = data.get("target_id", "")
        except: pass

def main():
    return ZepAssetMobileApp("ZepAsset", "org.z3pti.zepasset")

if __name__ == "__main__":
    main().main_loop()
