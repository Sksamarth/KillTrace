#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .setup(|app| {
      let about = tauri::menu::PredefinedMenuItem::about(app, Some("About KillChain AI"), None)?;
      let help = tauri::menu::Submenu::with_items(app, "Help", true, &[&about])?;
      app.set_menu(tauri::menu::Menu::with_items(app, &[&help])?)?;
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while building tauri application");
}
