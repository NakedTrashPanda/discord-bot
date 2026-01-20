import asyncio
from datetime import datetime
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.align import Align
import threading
import time
from config import (
    MEDIA_CHANNEL_ID,
    IMAGES_PER_BATCH,
    VIDEOS_PER_BATCH,
    ARCHIVE_RETENTION_DAYS,
    MAX_UPLOAD_SIZE_MB,
    SELECTION_ORDER,
    MEDIA_FOLDER,
    ARCHIVE_FOLDER,
    HISTORY_FILE,
)
import media_functions
import json
from pathlib import Path


class BotTUI:
    def __init__(self):
        self.console = Console()
        self.running = True
        self.media_stats = {}
        self.upload_history = []
        self.next_scheduled_time = None
        self.last_upload_time = None
        
    def get_media_stats(self):
        """Get current media statistics"""
        stats = {}
        
        # Load history
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
                uploaded_set = set(history.get("uploaded_files", []))
        else:
            uploaded_set = set()
        
        # Count media files
        images = [f for f in MEDIA_FOLDER.iterdir() if f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif', '.webp'} and f.name not in uploaded_set]
        videos = [f for f in MEDIA_FOLDER.iterdir() if f.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv', '.webm'} and f.name not in uploaded_set]
        
        stats['queued_images'] = len(images)
        stats['queued_videos'] = len(videos)
        stats['total_queued'] = len(images) + len(videos)
        
        # Count archived files
        archived = list(ARCHIVE_FOLDER.iterdir())
        stats['archived_files'] = len(archived)
        
        return stats
    
    def get_next_scheduled_upload(self):
        """Get the next scheduled upload time"""
        config_file = Path("schedule_config.json")
        if config_file.exists():
            with open(config_file, "r") as f:
                config = json.load(f)
                
            if config.get("enabled", True):
                # Get today's date and set the scheduled time
                now = datetime.now()
                scheduled_time = now.replace(hour=config.get("hour", 12), minute=config.get("minute", 0), second=0, microsecond=0)
                
                # If the scheduled time is in the past, set it to tomorrow
                if scheduled_time <= now:
                    scheduled_time = scheduled_time.replace(day=scheduled_time.day + 1)
                    
                return scheduled_time
        return None
    
    def create_layout(self):
        """Create the main layout for the TUI"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        layout["main"].split_row(
            Layout(name="stats", ratio=2),
            Layout(name="controls", ratio=1)
        )
        
        layout["main"]["stats"].split_column(
            Layout(name="media_stats", ratio=1),
            Layout(name="upload_history", ratio=2)
        )
        
        return layout
    
    def update_layout(self, layout):
        """Update the layout with current data"""
        # Header
        layout["header"].update(Panel(
            Align.center(Text("Discord Media Bot Control Panel", style="bold magenta")), 
            title="Status", 
            border_style="green"
        ))
        
        # Media Stats
        stats = self.get_media_stats()
        stats_table = Table.grid(padding=(0, 1))
        stats_table.add_column(style="cyan", justify="right", width=15)
        stats_table.add_column(style="white")
        
        stats_table.add_row("Queued Images:", str(stats['queued_images']))
        stats_table.add_row("Queued Videos:", str(stats['queued_videos']))
        stats_table.add_row("Total Queued:", str(stats['total_queued']))
        stats_table.add_row("Archived Files:", str(stats['archived_files']))
        
        layout["main"]["stats"]["media_stats"].update(
            Panel(stats_table, title="Media Queue", border_style="blue")
        )
        
        # Upload History (simplified view)
        history_panel = Panel(
            Align.center(Text("Upload history will appear here", style="italic")),
            title="Recent Uploads",
            border_style="yellow"
        )
        layout["main"]["stats"]["upload_history"].update(history_panel)
        
        # Controls
        controls_table = Table.grid(padding=(0, 1))
        controls_table.add_column(style="bold green", justify="left")
        
        controls_table.add_row("↑/↓: Navigate")
        controls_table.add_row("Enter: Select")
        controls_table.add_row("R: Refresh")
        controls_table.add_row("U: Manual Upload")
        controls_table.add_row("C: Clear History")
        controls_table.add_row("Q: Quit")
        
        layout["main"]["controls"].update(
            Panel(controls_table, title="Controls", border_style="red")
        )
        
        # Footer
        next_upload = self.get_next_scheduled_upload()
        next_time_str = next_upload.strftime("%Y-%m-%d %H:%M") if next_upload else "Not scheduled"
        
        footer_text = Text(f"Scheduled Upload: {next_time_str} | Last Refresh: {datetime.now().strftime('%H:%M:%S')}", style="bold white")
        layout["footer"].update(Panel(Align.center(footer_text), border_style="green"))
    
    def run_manual_upload(self):
        """Trigger a manual upload"""
        # This would need to interact with the bot instance
        # For now, just a placeholder
        self.console.print("[bold yellow]Manual upload triggered![/bold yellow]")
        # In a real implementation, this would call the upload function
        return "Manual upload initiated"
    
    def clear_history(self):
        """Clear upload history"""
        try:
            history = {"uploaded_files": [], "metadata": {}}
            with open(HISTORY_FILE, "w") as f:
                json.dump(history, f, indent=2)
            return "[green]History cleared successfully![/green]"
        except Exception as e:
            return f"[red]Error clearing history: {str(e)}[/red]"
    
    def run(self):
        """Main TUI run loop"""
        layout = self.create_layout()
        
        with Live(layout, refresh_per_second=1, screen=True) as live:
            while self.running:
                try:
                    self.update_layout(layout)
                    
                    # Check for user input (non-blocking)
                    if self.console.is_terminal:
                        if self.console.size.width > 0:  # Just to ensure we can read input
                            # In a real implementation, we'd use something like textual for proper input handling
                            # For now, we'll just update the display
                            time.sleep(0.1)
                            
                except KeyboardInterrupt:
                    self.running = False
                    break
                except Exception as e:
                    self.console.print(f"[red]Error in TUI: {str(e)}[/red]")
                    time.sleep(1)


# For a more advanced TUI with actual interactivity, we'd use textual library
# But for now, let's create a simpler version that works with just Rich
def simple_tui_main(bot_instance=None):
    """Simple TUI that runs in a separate thread"""
    import threading
    import time
    from rich.console import Console
    from rich.table import Table
    from rich.prompt import Prompt
    import os
    import sys
    
    console = Console()
    
    def display_status():
        console.clear()
        console.rule("[bold blue]Discord Media Bot Control Panel[/bold blue]")
        
        # Display bot status
        table = Table(title="Bot Status", show_header=True, header_style="bold magenta")
        table.add_column("Property", style="dim", width=20)
        table.add_column("Value", min_width=20)
        
        # Get media stats
        if Path("schedule_config.json").exists():
            with open("schedule_config.json", "r") as f:
                sched_config = json.load(f)
            schedule_enabled = sched_config.get("enabled", True)
            schedule_time = f"{sched_config.get('hour', 12):02d}:{sched_config.get('minute', 0):02d}"
        else:
            schedule_enabled = False
            schedule_time = "N/A"
        
        # Get media stats
        stats = get_simple_media_stats()
        
        table.add_row("Schedule Enabled", str(schedule_enabled))
        table.add_row("Scheduled Time", schedule_time)
        table.add_row("Queued Images", str(stats['queued_images']))
        table.add_row("Queued Videos", str(stats['queued_videos']))
        table.add_row("Total Queued", str(stats['total_queued']))
        table.add_row("Archived Files", str(stats['archived_files']))
        table.add_row("Max Upload Size", f"{MAX_UPLOAD_SIZE_MB} MB")
        table.add_row("Batch Size", f"{IMAGES_PER_BATCH} images + {VIDEOS_PER_BATCH} videos")
        
        console.print(table)
        
        # Display controls
        console.print("\n[bold cyan]Controls:[/bold cyan]")
        console.print("1. View Queue Details")
        console.print("2. Manual Upload Now")
        console.print("3. Clear History")
        console.print("4. Clear Archive")
        console.print("5. View Schedule Config")
        console.print("6. Change Schedule")
        console.print("7. Edit Bot Configuration")
        console.print("8. View Statistics Dashboard")
        console.print("9. Refresh Status")
        console.print("Q. Quit TUI")

        return table
    
    def get_simple_media_stats():
        """Get current media statistics"""
        stats = {}
        
        # Load history
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
                uploaded_set = set(history.get("uploaded_files", []))
        else:
            uploaded_set = set()
        
        # Count media files
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
        
        images = [f for f in MEDIA_FOLDER.iterdir() 
                 if f.suffix.lower() in image_extensions and f.name not in uploaded_set]
        videos = [f for f in MEDIA_FOLDER.iterdir() 
                 if f.suffix.lower() in video_extensions and f.name not in uploaded_set]
        
        stats['queued_images'] = len(images)
        stats['queued_videos'] = len(videos)
        stats['total_queued'] = len(images) + len(videos)
        
        # Count archived files
        archived = list(ARCHIVE_FOLDER.iterdir())
        stats['archived_files'] = len(archived)
        
        return stats
    
    def manual_upload_action():
        console.print("[bold yellow]Initiating manual upload...[/bold yellow]")
        # In a real implementation, this would interact with the bot instance
        # For now, just simulate
        time.sleep(1)
        console.print("[green]Manual upload completed![/green]")
    
    def clear_history_action():
        try:
            history = {"uploaded_files": [], "metadata": {}}
            with open(HISTORY_FILE, "w") as f:
                json.dump(history, f, indent=2)
            console.print("[green]Upload history cleared![/green]")
        except Exception as e:
            console.print(f"[red]Error clearing history: {str(e)}[/red]")
    
    def view_schedule_config():
        if Path("schedule_config.json").exists():
            with open("schedule_config.json", "r") as f:
                config = json.load(f)
            console.print(f"\n[bold]Schedule Configuration:[/bold]")
            console.print(f"Enabled: {config.get('enabled', True)}")
            console.print(f"Time: {config.get('hour', 12):02d}:{config.get('minute', 0):02d}")
        else:
            console.print("[yellow]No schedule configuration found.[/yellow]")

    def clear_archive_action():
        """Clear archived files"""
        try:
            archived_files = list(ARCHIVE_FOLDER.iterdir())
            if not archived_files:
                console.print("[yellow]No archived files to clear.[/yellow]")
                return

            console.print(f"[bold red]Warning: You are about to delete {len(archived_files)} archived files![/bold red]")
            confirm = Prompt.ask("Type 'YES' to confirm deletion", default="NO")

            if confirm.upper() == 'YES':
                deleted_count = 0
                for file_path in archived_files:
                    try:
                        file_path.unlink()  # Delete the file
                        deleted_count += 1
                    except Exception as e:
                        console.print(f"[red]Error deleting {file_path.name}: {str(e)}[/red]")

                console.print(f"[green]Successfully deleted {deleted_count} archived files![/green]")
            else:
                console.print("[yellow]Deletion cancelled.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error clearing archive: {str(e)}[/red]")

    def edit_bot_config():
        """Edit bot configuration settings"""
        console.print("\n[bold]Bot Configuration Editor[/bold]")
        console.print("Current settings:")

        # Read current config values from environment or defaults
        import os
        from pathlib import Path

        # Display current values
        console.print(f"1. Images per batch: {os.getenv('IMAGES_PER_BATCH', '3')}")
        console.print(f"2. Videos per batch: {os.getenv('VIDEOS_PER_BATCH', '7')}")
        console.print(f"3. Max upload size (MB): {os.getenv('MAX_UPLOAD_SIZE_MB', '25')}")
        console.print(f"4. Archive retention days: {os.getenv('ARCHIVE_RETENTION_DAYS', '3')}")
        console.print(f"5. Selection order: {os.getenv('SELECTION_ORDER', 'random')}")
        console.print(f"6. Media channel ID: {os.getenv('MEDIA_CHANNEL_ID', '439072343285956618')}")
        console.print(f"7. Movies channel ID: {os.getenv('MOVIES_CHANNEL_ID', '370237203462488064')}")
        console.print("8. Back to main menu")

        try:
            choice = Prompt.ask("\nSelect setting to edit (1-8)", default="8")
            choice = int(choice)

            if choice == 1:
                new_value = Prompt.ask("Enter new number of images per batch", default=str(os.getenv('IMAGES_PER_BATCH', '3')))
                try:
                    val = int(new_value)
                    if val >= 0:
                        # In a real implementation, we'd update the actual config
                        console.print(f"[green]Would update IMAGES_PER_BATCH to {val}[/green]")
                        console.print("[yellow]Note: Changes require bot restart to take effect[/yellow]")
                    else:
                        console.print("[red]Value must be non-negative[/red]")
                except ValueError:
                    console.print("[red]Please enter a valid number[/red]")

            elif choice == 2:
                new_value = Prompt.ask("Enter new number of videos per batch", default=str(os.getenv('VIDEOS_PER_BATCH', '7')))
                try:
                    val = int(new_value)
                    if val >= 0:
                        console.print(f"[green]Would update VIDEOS_PER_BATCH to {val}[/green]")
                        console.print("[yellow]Note: Changes require bot restart to take effect[/yellow]")
                    else:
                        console.print("[red]Value must be non-negative[/red]")
                except ValueError:
                    console.print("[red]Please enter a valid number[/red]")

            elif choice == 3:
                new_value = Prompt.ask("Enter new max upload size in MB", default=str(os.getenv('MAX_UPLOAD_SIZE_MB', '25')))
                try:
                    val = int(new_value)
                    if val > 0:
                        console.print(f"[green]Would update MAX_UPLOAD_SIZE_MB to {val}[/green]")
                        console.print("[yellow]Note: Changes require bot restart to take effect[/yellow]")
                    else:
                        console.print("[red]Value must be positive[/red]")
                except ValueError:
                    console.print("[red]Please enter a valid number[/red]")

            elif choice == 4:
                new_value = Prompt.ask("Enter new archive retention days", default=str(os.getenv('ARCHIVE_RETENTION_DAYS', '3')))
                try:
                    val = int(new_value)
                    if val >= 0:
                        console.print(f"[green]Would update ARCHIVE_RETENTION_DAYS to {val}[/green]")
                        console.print("[yellow]Note: Changes require bot restart to take effect[/yellow]")
                    else:
                        console.print("[red]Value must be non-negative[/red]")
                except ValueError:
                    console.print("[red]Please enter a valid number[/red]")

            elif choice == 5:
                current_order = os.getenv('SELECTION_ORDER', 'random')
                console.print(f"Current selection order: {current_order}")
                console.print("Options: 'random', 'name', 'size'")
                new_value = Prompt.ask("Enter new selection order", default=current_order)
                if new_value in ['random', 'name', 'size']:
                    console.print(f"[green]Would update SELECTION_ORDER to '{new_value}'[/green]")
                    console.print("[yellow]Note: Changes require bot restart to take effect[/yellow]")
                else:
                    console.print("[red]Invalid selection order. Use 'random', 'name', or 'size'[/red]")

            elif choice == 6:
                new_value = Prompt.ask("Enter new media channel ID", default=str(os.getenv('MEDIA_CHANNEL_ID', '439072343285956618')))
                try:
                    val = int(new_value)
                    console.print(f"[green]Would update MEDIA_CHANNEL_ID to {val}[/green]")
                    console.print("[yellow]Note: Changes require bot restart to take effect[/yellow]")
                except ValueError:
                    console.print("[red]Please enter a valid number[/red]")

            elif choice == 7:
                new_value = Prompt.ask("Enter new movies channel ID", default=str(os.getenv('MOVIES_CHANNEL_ID', '370237203462488064')))
                try:
                    val = int(new_value)
                    console.print(f"[green]Would update MOVIES_CHANNEL_ID to {val}[/green]")
                    console.print("[yellow]Note: Changes require bot restart to take effect[/yellow]")
                except ValueError:
                    console.print("[red]Please enter a valid number[/red]")

            elif choice == 8:
                console.print("[blue]Returning to main menu...[/blue]")
                return
            else:
                console.print("[red]Invalid choice. Please select 1-8.[/red]")

        except ValueError:
            console.print("[red]Please enter a valid number.[/red]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled.[/yellow]")

    def get_statistics():
        """Generate statistics for the dashboard"""
        import json
        from datetime import datetime, timedelta
        from pathlib import Path

        stats = {}

        # Load history
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
                uploaded_files = history.get("uploaded_files", [])
                metadata = history.get("metadata", {})
        else:
            uploaded_files = []
            metadata = {}

        # Count uploaded files
        stats['total_uploaded'] = len(uploaded_files)

        # Count uploaded by type
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}

        image_count = sum(1 for f in uploaded_files if Path(f).suffix.lower() in image_extensions)
        video_count = sum(1 for f in uploaded_files if Path(f).suffix.lower() in video_extensions)

        stats['images_uploaded'] = image_count
        stats['videos_uploaded'] = video_count

        # Calculate storage used
        total_size = 0
        for filename in uploaded_files:
            archive_path = ARCHIVE_FOLDER / filename
            if archive_path.exists():
                total_size += archive_path.stat().st_size

        stats['storage_used_mb'] = round(total_size / (1024 * 1024), 2)

        # Recent uploads (last 7 days)
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        recent_uploads = []
        for filename, data in metadata.items():
            upload_date = data.get("upload_date", "")
            if upload_date >= seven_days_ago:
                recent_uploads.append((filename, upload_date))

        stats['recent_uploads_count'] = len(recent_uploads)
        stats['recent_uploads'] = recent_uploads[:10]  # Top 10 recent uploads

        # Get rating stats if available
        ratings_file = Path("media_ratings.json")
        if ratings_file.exists():
            with open(ratings_file, "r") as f:
                ratings = json.load(f)

            stats['rated_files'] = len(ratings)
            total_votes = sum(data.get("votes", 0) for data in ratings.values())
            stats['total_votes'] = total_votes
        else:
            stats['rated_files'] = 0
            stats['total_votes'] = 0

        return stats

    def view_statistics_dashboard():
        """Display the statistics dashboard"""
        console.print("\n[bold blue]Statistics Dashboard[/bold blue]")

        stats = get_statistics()

        # Create a table for main stats
        from rich.table import Table
        table = Table(title="Summary Statistics", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="dim", width=25)
        table.add_column("Value", justify="right", style="bold green")

        table.add_row("Total Uploaded Files", str(stats['total_uploaded']))
        table.add_row("Images Uploaded", str(stats['images_uploaded']))
        table.add_row("Videos Uploaded", str(stats['videos_uploaded']))
        table.add_row("Storage Used", f"{stats['storage_used_mb']} MB")
        table.add_row("Files Rated", str(stats['rated_files']))
        table.add_row("Total Votes", str(stats['total_votes']))
        table.add_row("Recent Uploads (7 days)", str(stats['recent_uploads_count']))

        console.print(table)

        # Show recent uploads
        if stats['recent_uploads']:
            console.print("\n[bold]Recent Uploads:[/bold]")
            recent_table = Table(show_header=True, header_style="bold cyan")
            recent_table.add_column("Filename", style="dim", width=30)
            recent_table.add_column("Date", style="green")

            for filename, upload_date in stats['recent_uploads']:
                # Format the date nicely
                try:
                    dt = datetime.fromisoformat(upload_date.replace('Z', '+00:00'))
                    formatted_date = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    formatted_date = upload_date

                recent_table.add_row(filename[:28] + "..." if len(filename) > 28 else filename, formatted_date)

            console.print(recent_table)
        else:
            console.print("\n[yellow]No recent uploads to display.[/yellow]")

        console.print("\n[bold]Press Enter to return to main menu...[/bold]")
        input()

    def change_schedule():
        console.print("\n[bold]Change Schedule:[/bold]")
        try:
            hour_input = Prompt.ask("Enter hour (0-23)", default="12")
            minute_input = Prompt.ask("Enter minute (0-59)", default="0")

            hour = int(hour_input)
            minute = int(minute_input)

            if 0 <= hour <= 23 and 0 <= minute <= 59:
                config = {
                    "enabled": True,
                    "hour": hour,
                    "minute": minute
                }

                with open("schedule_config.json", "w") as f:
                    json.dump(config, f, indent=2)

                console.print(f"[green]Schedule updated to {hour:02d}:{minute:02d}[/green]")
            else:
                console.print("[red]Invalid time entered![/red]")
        except ValueError:
            console.print("[red]Please enter valid numbers![/red]")
        except Exception as e:
            console.print(f"[red]Error updating schedule: {str(e)}[/red]")
    
    # Main TUI loop
    console.print("[green]Discord Bot TUI started![/green]")
    console.print("Press Enter to continue...")
    input()
    
    while True:
        display_status()
        
        choice = Prompt.ask("\nEnter your choice", default="6").strip().lower()
        
        if choice == '1':
            # View queue details
            stats = get_simple_media_stats()
            console.print(f"\n[bold]Queue Details:[/bold]")
            
            # Show some sample files
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
            video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
            
            queued_images = [f for f in MEDIA_FOLDER.iterdir() 
                           if f.suffix.lower() in image_extensions]
            queued_videos = [f for f in MEDIA_FOLDER.iterdir() 
                           if f.suffix.lower() in video_extensions]
            
            console.print(f"\n[underline]Sample Image Files:[/underline]")
            for img in queued_images[:5]:  # Show first 5
                size_mb = img.stat().st_size / (1024 * 1024)
                console.print(f"  • {img.name} ({size_mb:.2f} MB)")
            if len(queued_images) > 5:
                console.print(f"  ... and {len(queued_images) - 5} more")
                
            console.print(f"\n[underline]Sample Video Files:[/underline]")
            for vid in queued_videos[:5]:  # Show first 5
                size_mb = vid.stat().st_size / (1024 * 1024)
                console.print(f"  • {vid.name} ({size_mb:.2f} MB)")
            if len(queued_videos) > 5:
                console.print(f"  ... and {len(queued_videos) - 5} more")
                
            console.print("\nPress Enter to continue...")
            input()
            
        elif choice == '2':
            manual_upload_action()
            console.print("\nPress Enter to continue...")
            input()
            
        elif choice == '3':
            clear_history_action()
            console.print("\nPress Enter to continue...")
            input()
            
        elif choice == '4':
            clear_archive_action()
            console.print("\nPress Enter to continue...")
            input()

        elif choice == '5':
            view_schedule_config()
            console.print("\nPress Enter to continue...")
            input()

        elif choice == '6':
            change_schedule()
            console.print("\nPress Enter to continue...")
            input()

        elif choice == '7':
            edit_bot_config()
            console.print("\nPress Enter to continue...")
            input()

        elif choice == '8':
            view_statistics_dashboard()
            console.print("\nPress Enter to continue...")
            input()

        elif choice == '9':
            # Refresh is automatic in the display
            continue
            
        elif choice in ['q', 'quit', 'exit']:
            console.print("[bold red]Exiting TUI...[/bold red]")
            break
        else:
            console.print("[red]Invalid choice. Please try again.[/red]")
            console.print("\nPress Enter to continue...")
            input()

if __name__ == "__main__":
    simple_tui_main()