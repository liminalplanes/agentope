import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useState,
} from "react";

export type ThemeChoice = "light" | "dark" | "system";

const STORAGE_KEY = "agentope-theme";

/** Runs before first paint (inlined in <head>) so the page never flashes the wrong theme. */
export const themeInitScript = `(function(){document.documentElement.classList.add('js');try{var c=localStorage.getItem('${STORAGE_KEY}')||'system';var d=c==='dark'||(c==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',d);}catch(e){if(matchMedia('(prefers-color-scheme: dark)').matches)document.documentElement.classList.add('dark');}})();`;

function readChoice(): ThemeChoice {
	try {
		const value = localStorage.getItem(STORAGE_KEY);
		return value === "light" || value === "dark" ? value : "system";
	} catch {
		return "system";
	}
}

function apply(choice: ThemeChoice) {
	const dark =
		choice === "dark" ||
		(choice === "system" &&
			window.matchMedia("(prefers-color-scheme: dark)").matches);
	document.documentElement.classList.toggle("dark", dark);
}

const ThemeContext = createContext<{
	choice: ThemeChoice;
	setChoice: (choice: ThemeChoice) => void;
}>({ choice: "system", setChoice: () => {} });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
	const [choice, setChoiceState] = useState<ThemeChoice>("system");

	useEffect(() => {
		setChoiceState(readChoice());
	}, []);

	useEffect(() => {
		if (choice !== "system") return;
		const media = window.matchMedia("(prefers-color-scheme: dark)");
		const onChange = () => apply("system");
		media.addEventListener("change", onChange);
		return () => media.removeEventListener("change", onChange);
	}, [choice]);

	const setChoice = useCallback((next: ThemeChoice) => {
		setChoiceState(next);
		try {
			localStorage.setItem(STORAGE_KEY, next);
		} catch {
			// Storage can be unavailable (private windows); the choice still applies to this visit.
		}
		apply(next);
	}, []);

	return (
		<ThemeContext.Provider value={{ choice, setChoice }}>
			{children}
		</ThemeContext.Provider>
	);
}

export function useTheme() {
	return useContext(ThemeContext);
}
