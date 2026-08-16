mod commands;
mod state;

use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let dir = app.path().app_data_dir()?;
            app.manage(state::AppState::load(dir));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::compute_return,
            commands::supported,
            commands::get_settings,
            commands::set_provider,
            commands::grant_consent,
            commands::revoke_consent,
            commands::advisor_chat,
            commands::storage_status,
            commands::list_returns,
            commands::save_return,
            commands::load_return,
            commands::delete_return,
            commands::autofill_import,
            commands::autofill_apply,
            commands::rrsp_plan,
            commands::cca_plan,
            commands::licence_status,
            commands::install_licence,
            commands::install_licence_file,
            commands::remove_licence,
            commands::filing_gate,
            commands::couple_optimize,
        ])
        .run(tauri::generate_context!())
        .expect("Freshet failed to start");
}
