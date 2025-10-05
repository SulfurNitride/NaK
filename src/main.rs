use iced::{
    widget::{button, column, container, row, text, Column},
    Application, Command, Element, Settings, Theme,
};
use std::process::Command as ProcessCommand;
use std::path::Path;

#[derive(Debug, Clone)]
enum Message {
    ScanGames,
    CheckDependencies,
    ModManagers,
    InstallMO2,
    LaunchMO2,
    ClearLogs,
}

struct NaKGui {
    logs: Vec<String>,
    game_count: u32,
    status: String,
    games: Vec<Game>,
    dependencies_status: String,
    dependencies_checked: bool,
    show_mod_managers: bool,
}

#[derive(Debug, Clone)]
struct Game {
    name: String,
    path: String,
    platform: String,
}

impl Application for NaKGui {
    type Executor = iced::executor::Default;
    type Flags = ();
    type Message = Message;
    type Theme = Theme;

    fn new(_flags: ()) -> (Self, Command<Message>) {
        (
            Self {
                logs: vec!["NaK Linux Modding Helper started".to_string()],
                game_count: 0,
                status: "Ready".to_string(),
                games: Vec::new(),
                dependencies_status: "Checking...".to_string(),
                dependencies_checked: false,
                show_mod_managers: false,
            },
            Command::perform(async {}, |_| Message::CheckDependencies),
        )
    }

    fn title(&self) -> String {
        String::from("NaK Linux Modding Helper")
    }

    fn update(&mut self, message: Message) -> Command<Message> {
        match message {
        Message::ScanGames => {
            self.logs.push("Scanning for games...".to_string());
            
            // Execute Python backend - try multiple possible paths
            let backend_paths = ["./nak-backend", "./dist/nak_backend", "/usr/bin/nak-backend"];
            let mut output_result = None;
            
            for backend_path in &backend_paths {
                if let Ok(output) = ProcessCommand::new(backend_path)
                    .arg("--scan-games")
                    .output()
                {
                    output_result = Some((output, backend_path));
                    break;
                }
            }
            
            if let Some((output, used_path)) = output_result {
                if output.status.success() {
                    let result = String::from_utf8_lossy(&output.stdout);
                    self.logs.push(format!("Backend found at: {}", used_path));
                    self.logs.push(format!("Full JSON length: {} characters", result.len()));
                    
                    // Try to parse JSON response and extract games
                    match serde_json::from_str::<serde_json::Value>(&result) {
                        Ok(json) => {
                        self.logs.push("JSON parsing successful".to_string());
                        
                        if let Some(count) = json.get("count").and_then(|v| v.as_u64()) {
                            self.game_count = count as u32;
                            self.logs.push(format!("Set game count to: {}", self.game_count));
                        } else {
                            self.logs.push("No count field found in JSON".to_string());
                        }
                        
                        // Parse games array
                        if let Some(games_array) = json.get("games").and_then(|v| v.as_array()) {
                            self.logs.push(format!("Found games array with {} items", games_array.len()));
                            self.games.clear();
                            for (i, game_json) in games_array.iter().enumerate() {
                                if let (Some(name), Some(path), Some(platform)) = (
                                    game_json.get("name").and_then(|v| v.as_str()),
                                    game_json.get("path").and_then(|v| v.as_str()),
                                    game_json.get("platform").and_then(|v| v.as_str()),
                                ) {
                                    self.games.push(Game {
                                        name: name.to_string(),
                                        path: path.to_string(),
                                        platform: platform.to_string(),
                                    });
                                    if i < 3 { // Log first 3 games for debugging
                                        self.logs.push(format!("Added game #{}: {}", i+1, name));
                                    }
                                }
                            }
                            self.logs.push(format!("Parsed {} games successfully", self.games.len()));
                        } else {
                            self.logs.push("No games array found in JSON response".to_string());
                        }
                            self.status = "Games scanned successfully".to_string();
                        }
                        Err(e) => {
                            self.logs.push("=== JSON PARSING ERROR ===".to_string());
                            self.logs.push(format!("Error: {}", e));
                            self.logs.push(format!("Line: {}, Column: {}", e.line(), e.column()));
                            self.status = format!("JSON parse error at line {}", e.line());
                        }
                    }
                } else {
                    let error = String::from_utf8_lossy(&output.stderr);
                    self.logs.push(format!("Error: {}", error));
                    self.status = "Game scan failed".to_string();
                }
            } else {
                self.logs.push("Failed to execute Python backend at any location".to_string());
                self.status = "Backend not found".to_string();
            }
        }
            Message::CheckDependencies => {
                // Only run once
                if self.dependencies_checked {
                    return Command::none();
                }
                self.dependencies_checked = true;
                
                // Execute Python backend - try multiple possible paths
                let backend_paths = ["./nak-backend", "./dist/nak_backend", "/usr/bin/nak-backend"];
                let mut output_result = None;
                
                for backend_path in &backend_paths {
                    if let Ok(output) = ProcessCommand::new(backend_path)
                        .arg("--check-dependencies")
                        .output()
                    {
                        output_result = Some((output, backend_path));
                        break;
                    }
                }
                
                if let Some((output, _used_path)) = output_result {
                    if output.status.success() {
                        let result = String::from_utf8_lossy(&output.stdout);
                        // Parse the JSON to check what's missing
                        if let Ok(json) = serde_json::from_str::<serde_json::Value>(&result) {
                            if let Some(deps) = json.get("dependencies").and_then(|v| v.as_object()) {
                                let mut missing = Vec::new();
                                for (name, info) in deps {
                                    if let Some(installed) = info.get("installed").and_then(|v| v.as_bool()) {
                                        if !installed {
                                            missing.push(name.clone());
                                        }
                                    }
                                }
                                if missing.is_empty() {
                                    self.dependencies_status = "All dependencies OK".to_string();
                                } else {
                                    self.dependencies_status = format!("Missing: {}", missing.join(", "));
                                    self.logs.push(format!("Missing dependencies: {}", missing.join(", ")));
                                }
                            }
                        }
                    } else {
                        self.dependencies_status = "Check failed".to_string();
                    }
                } else {
                    self.dependencies_status = "Backend not found".to_string();
                }
            }
            Message::ModManagers => {
                self.show_mod_managers = !self.show_mod_managers;
                // Toggle menu without spamming logs
            }
            Message::InstallMO2 => {
                self.logs.push("Installing Mod Organizer 2...".to_string());
                
                let backend_paths = ["./nak-backend", "./dist/nak_backend", "/usr/bin/nak-backend"];
                let mut output_result = None;
                
                for backend_path in &backend_paths {
                    if let Ok(output) = ProcessCommand::new(backend_path)
                        .arg("--install-mo2")
                        .output()
                    {
                        output_result = Some((output, backend_path));
                        break;
                    }
                }
                
                if let Some((output, _used_path)) = output_result {
                    if output.status.success() {
                        let result = String::from_utf8_lossy(&output.stdout);
                        self.logs.push(format!("Backend response: {}", result));
                        self.status = "MO2 installation started".to_string();
                    } else {
                        let error = String::from_utf8_lossy(&output.stderr);
                        self.logs.push(format!("Error: {}", error));
                        self.status = "MO2 installation failed".to_string();
                    }
                } else {
                    self.logs.push("Failed to execute Python backend".to_string());
                    self.status = "Backend not found".to_string();
                }
            }
            Message::LaunchMO2 => {
                self.logs.push("Launching Mod Organizer 2...".to_string());
                
                let backend_paths = ["./nak-backend", "./dist/nak_backend", "/usr/bin/nak-backend"];
                let mut output_result = None;
                
                for backend_path in &backend_paths {
                    if let Ok(output) = ProcessCommand::new(backend_path)
                        .arg("--launch-mo2")
                        .output()
                    {
                        output_result = Some((output, backend_path));
                        break;
                    }
                }
                
                if let Some((output, _used_path)) = output_result {
                    if output.status.success() {
                        let result = String::from_utf8_lossy(&output.stdout);
                        self.logs.push(format!("Backend response: {}", result));
                        self.status = "MO2 launched".to_string();
                    } else {
                        let error = String::from_utf8_lossy(&output.stderr);
                        self.logs.push(format!("Error: {}", error));
                        self.status = "MO2 launch failed".to_string();
                    }
                } else {
                    self.logs.push("Failed to execute Python backend".to_string());
                    self.status = "Backend not found".to_string();
                }
            }
            Message::ClearLogs => {
                self.logs.clear();
                self.logs.push("Logs cleared".to_string());
            }
        }
        Command::none()
    }

    fn view(&self) -> Element<Message> {
        let mut sidebar_items = vec![
            text("NaK").size(24).style(iced::theme::Text::Color(iced::Color::from_rgb(0.0, 1.0, 1.0))).into(),
            button("Scan Games").on_press(Message::ScanGames).into(),
            button(if self.show_mod_managers { "Mod Managers v" } else { "Mod Managers >" })
                .on_press(Message::ModManagers).into(),
        ];
        
        // Show MO2 options if Mod Managers is expanded
        if self.show_mod_managers {
            sidebar_items.push(
                container(button("Install MO2").on_press(Message::InstallMO2))
                    .padding([0, 0, 0, 20])
                    .into()
            );
            sidebar_items.push(
                container(button("Launch MO2").on_press(Message::LaunchMO2))
                    .padding([0, 0, 0, 20])
                    .into()
            );
        }
        
        sidebar_items.push(button("Clear Logs").on_press(Message::ClearLogs).into());
        
        let sidebar = Column::with_children(sidebar_items)
            .spacing(10)
            .padding(20);

        let log_content = Column::with_children(
            self.logs
                .iter()
                .map(|log| {
                    text(log)
                        .style(iced::theme::Text::Color(iced::Color::from_rgb(0.0, 0.8, 0.8)))
                        .size(12)
                        .into()
                })
                .collect::<Vec<_>>(),
        )
        .spacing(5);

        // Create game list content as a grid of cards
        let game_list_content = if self.games.is_empty() {
            Column::new().push(text("No games found. Click 'Scan Games' to search."))
        } else {
            // Create game cards in rows (3 per row)
            let mut rows = Vec::new();
            let games_per_row = 3;
            
            for chunk in self.games.chunks(games_per_row) {
                let mut row_items = Vec::new();
                
                for game in chunk {
                    let card = container(
                        column![
                            text(&game.name)
                                .style(iced::theme::Text::Color(iced::Color::BLACK))
                                .size(14),
                            text(&game.platform)
                                .style(iced::theme::Text::Color(iced::Color::from_rgb(0.3, 0.3, 0.3)))
                                .size(11),
                        ]
                        .spacing(5)
                        .padding(12)
                    )
                    .width(iced::Length::Fill)
                    .height(iced::Length::Fixed(80.0))
                    .padding(8)
                    .style(|_theme: &iced::Theme| {
                        iced::widget::container::Appearance {
                            background: Some(iced::Background::Color(iced::Color::WHITE)),
                            border: iced::Border {
                                color: iced::Color::from_rgb(0.8, 0.8, 0.8),
                                width: 1.0,
                                radius: 8.0.into(),
                            },
                            ..Default::default()
                        }
                    });
                    
                    row_items.push(card.into());
                }
                
                // Add the row
                let game_row = row(row_items).spacing(10);
                rows.push(game_row.into());
            }
            
            Column::with_children(rows).spacing(10)
        };

        let main_content = column![
            text("NaK Linux Modding Helper")
                .size(28)
                .style(iced::theme::Text::Color(iced::Color::from_rgb(0.0, 1.0, 1.0))),
            text(format!("Status: {}", self.status))
                .style(iced::theme::Text::Color(iced::Color::from_rgb(0.0, 0.8, 0.8))),
            text(format!("Dependencies: {}", self.dependencies_status))
                .style(iced::theme::Text::Color(
                    if self.dependencies_status.contains("OK") {
                        iced::Color::from_rgb(0.0, 1.0, 0.0)
                    } else if self.dependencies_status.contains("Missing") {
                        iced::Color::from_rgb(1.0, 0.5, 0.0)
                    } else {
                        iced::Color::from_rgb(0.0, 0.8, 0.8)
                    }
                )),
            text(format!("Games Found: {}", self.game_count))
                .style(iced::theme::Text::Color(iced::Color::from_rgb(0.0, 0.8, 0.8))),
            text("Game List:").size(16).style(iced::theme::Text::Color(iced::Color::from_rgb(0.0, 1.0, 1.0))),
            container(
                iced::widget::scrollable(game_list_content)
            )
                .width(iced::Length::Fill)
                .height(iced::Length::FillPortion(3))
                .padding(10),
            text("Logs:").size(16).style(iced::theme::Text::Color(iced::Color::from_rgb(0.0, 1.0, 1.0))),
            container(
                iced::widget::scrollable(log_content)
            )
                .width(iced::Length::Fill)
                .height(iced::Length::FillPortion(2))
                .padding(10),
        ]
        .spacing(10)
        .padding(20);

        let content = row![
            container(sidebar)
                .width(iced::Length::Fixed(200.0)),
            container(main_content)
                .width(iced::Length::Fill)
                .height(iced::Length::Fill)
        ]
        .spacing(20);

        container(content)
            .width(iced::Length::Fill)
            .height(iced::Length::Fill)
            .padding(10)
            .style(|_theme: &iced::Theme| {
                iced::widget::container::Appearance {
                    background: Some(iced::Background::Color(iced::Color::BLACK)),
                    ..Default::default()
                }
            })
            .into()
    }

    fn theme(&self) -> Theme {
        Theme::Dark
    }
}

fn main() -> iced::Result {
    NaKGui::run(Settings {
        window: iced::window::Settings {
            size: iced::Size::new(1200.0, 800.0),
            min_size: Some(iced::Size::new(800.0, 600.0)),
            ..Default::default()
        },
        ..Default::default()
    })
}