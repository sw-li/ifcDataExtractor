"""
IFC Extractor — Entry Point
Launches the Tkinter UI.
"""

from ui.app import IFCExtractorApp


def main():
    app = IFCExtractorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
