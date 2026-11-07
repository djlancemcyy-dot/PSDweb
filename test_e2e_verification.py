import time
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

output_screenshots_dir = Path(r"C:\Users\lee\Downloads\PSD-m\PSDweb\test_screenshots")
output_screenshots_dir.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1600, "height": 950})
    page = context.new_page()

    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    print("[E2E] Navigating to http://127.0.0.1:8765 ...")
    page.goto("http://127.0.0.1:8765", wait_until="networkidle")
    time.sleep(1.5)

    # 1. Verify Workspace and Canvas layout
    canvas = page.locator("#canvas-scroll-container")
    drawer = page.locator("#bottom-drawer")
    stage = page.locator("#sheet-stage")

    canvas_box = canvas.bounding_box()
    drawer_box = drawer.bounding_box()
    stage_box = stage.bounding_box()

    print(f"[E2E] Canvas bbox: {canvas_box}")
    print(f"[E2E] Drawer bbox: {drawer_box}")
    print(f"[E2E] Stage bbox: {stage_box}")

    assert canvas_box["width"] > 600, f"Canvas width too small ({canvas_box['width']}), possible layout collapse!"
    assert drawer_box["y"] > canvas_box["y"], "Drawer should be below canvas, not inside it horizontally!"

    # Screenshot 1: Main workspace
    p1 = output_screenshots_dir / "01_main_workspace.png"
    page.screenshot(path=str(p1))
    print(f"[E2E] Captured: {p1}")

    # 2. Verify Settings modal (Only Output Path, No AI Models)
    btn_settings = page.locator("#btn-open-settings")
    btn_settings.click()
    page.wait_for_selector("#modal-settings.show")
    time.sleep(0.5)

    modal_settings = page.locator("#modal-settings")
    # Verify no model cards in modal-settings
    model_cards_in_settings = page.locator("#modal-settings .model-cards-grid")
    assert model_cards_in_settings.count() == 0, "Model cards should NOT be inside modal-settings!"

    # Verify input field, browse button, and save button exist
    assert page.locator("#settings-output-dir").is_visible(), "Output dir input must be visible!"
    assert page.locator("#btn-browse-output-dir").is_visible(), "Browse folder button must be visible!"
    assert page.locator("#btn-save-settings").is_visible(), "Save button must be visible!"

    p2 = output_screenshots_dir / "02_settings_modal_clean.png"
    page.screenshot(path=str(p2))
    print(f"[E2E] Captured: {p2}")

    # Close settings modal
    page.locator("#btn-close-settings-modal").click()
    time.sleep(0.3)

    # 3. Verify Dedicated AI Cutout Models modal
    btn_quick_model = page.locator("#btn-quick-model-select")
    btn_quick_model.click()
    page.wait_for_selector("#modal-cutout-models.show")
    time.sleep(0.5)

    modal_models = page.locator("#modal-cutout-models")
    cards = page.locator("#modal-cutout-models .model-select-card")
    print(f"[E2E] Cutout model cards count: {cards.count()}")
    assert cards.count() >= 4, "Should have 4 AI cutout models!"

    p3 = output_screenshots_dir / "03_cutout_models_modal.png"
    page.screenshot(path=str(p3))
    print(f"[E2E] Captured: {p3}")

    # Close cutout models modal
    page.locator("#btn-close-models-modal").click()
    time.sleep(0.3)

    # 4. Verify Hand Tool button
    btn_hand = page.locator("#btn-toggle-hand-tool")
    assert btn_hand.is_visible(), "Hand tool button must be visible!"
    btn_hand.click()
    time.sleep(0.3)
    assert "active" in btn_hand.get_attribute("class"), "Hand tool should be active after click!"

    p4 = output_screenshots_dir / "04_hand_tool_active.png"
    page.screenshot(path=str(p4))
    print(f"[E2E] Captured: {p4}")

    # 5. Test PSD Render Speed via API
    print("[E2E] Testing /api/render performance...")
    t0 = time.time()
    task_res = page.evaluate("""async () => {
        const task = getActiveTask();
        const payload = {
            id: task.id,
            name: task.name,
            sku: task.sku,
            material_code: task.material_code,
            season: task.season,
            category: task.category,
            craft: task.craft,
            size: task.size,
            fabrics: task.fabrics,
            soles: task.soles,
            shoes: task.shoes.map(s => ({
                id: s.id,
                color_name: s.color_name,
                raw_filename: s.raw_filename,
                cutout_filename: s.cutout_filename,
                is_cutout: s.is_cutout,
                scale_multiplier: s.scale_multiplier || 1.0,
                offset_x: s.offset_x || 0.0,
                offset_y: s.offset_y || 0.0,
                logos: (s.logos || []).map(l => ({
                    logo_id: l.logo_id,
                    rel_x: l.rel_x,
                    rel_y: l.rel_y,
                    scale: l.scale,
                    rotation: l.rotation || 0
                }))
            }))
        };
        const res = await fetch('/api/render', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        return await res.json();
    }""")
    render_duration = time.time() - t0
    print(f"[E2E] Render duration: {render_duration:.3f}s")
    print(f"[E2E] Render response: {task_res}")

    assert task_res["status"] == "success", f"Render failed: {task_res}"
    assert task_res["has_psd"] is True, "PSD file must be generated!"
    assert render_duration < 3.0, f"Render took too long ({render_duration:.2f}s)! Must be sub-3 seconds."
    
    psd_file = Path(task_res["psd_filepath"])
    assert psd_file.exists(), f"Generated PSD file not found on disk: {psd_file}"
    psd_size_mb = psd_file.stat().st_size / (1024 * 1024)
    print(f"[E2E] PSD successfully generated! Path: {psd_file}, Size: {psd_size_mb:.2f} MB")

    browser.close()

print(f"[E2E] Console errors ({len(console_errors)}): {console_errors}")
print("[E2E] ALL AUTOMATION TESTS PASSED 100%!")
