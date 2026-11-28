import { useState } from "react";
import type { ComputeTier, GoalType, StudentProfile } from "../types";

interface AuthProfileViewProps {
  isAuthenticated: boolean;
  userEmail: string;
  profile: StudentProfile | null;
  onAuth: (mode: "login" | "register", email: string, password: string) => Promise<void>;
  onSaveProfile: (payload: {
    skills: string[];
    hours_per_week: number;
    weeks_available: number;
    team_size: number;
    compute: ComputeTier;
    goal: GoalType;
    interests: string[];
  }) => Promise<void>;
}

export function AuthProfileView({
  isAuthenticated,
  userEmail,
  profile,
  onAuth,
  onSaveProfile,
}: AuthProfileViewProps) {
  const [authMode, setAuthMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [skills, setSkills] = useState(profile?.skills.join(", ") || "python, react");
  const [hoursPerWeek, setHoursPerWeek] = useState(String(profile?.hours_per_week ?? 12));
  const [weeksAvailable, setWeeksAvailable] = useState(String(profile?.weeks_available ?? 10));
  const [teamSize, setTeamSize] = useState(String(profile?.team_size ?? 2));
  const [compute, setCompute] = useState<ComputeTier>(profile?.compute ?? "laptop");
  const [goal, setGoal] = useState<GoalType>(profile?.goal ?? "portfolio");
  const [interests, setInterests] = useState(
    profile?.interests.join(", ") || "devtools, education"
  );

  if (!isAuthenticated) {
    return (
      <section className="card" aria-label="Authentication">
        <h2>{authMode === "register" ? "Create Account" : "Sign In"}</h2>
        <div className="nav-tabs" style={{ marginBottom: 12 }}>
          <button
            type="button"
            className={authMode === "register" ? "tab-btn active" : "tab-btn"}
            onClick={() => setAuthMode("register")}
          >
            Register
          </button>
          <button
            type="button"
            className={authMode === "login" ? "tab-btn active" : "tab-btn"}
            onClick={() => setAuthMode("login")}
          >
            Login
          </button>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void onAuth(authMode, email, password);
          }}
        >
          <label>
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="student@nu.edu.pk"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button type="submit" className="primary">
            {authMode === "register" ? "Create Account" : "Sign In"}
          </button>
        </form>
      </section>
    );
  }

  return (
    <section className="card" aria-label="Student Profile">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Student Profile ({userEmail})</h2>
        {profile && (
          <span className="badge STABLE">Profile v{profile.profile_version}</span>
        )}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void onSaveProfile({
            skills: skills.split(",").map((s) => s.trim()).filter(Boolean),
            hours_per_week: Number(hoursPerWeek),
            weeks_available: Number(weeksAvailable),
            team_size: Number(teamSize),
            compute,
            goal,
            interests: interests.split(",").map((s) => s.trim()).filter(Boolean),
          });
        }}
      >
        <div className="grid-2">
          <label>
            Skills (comma-separated)
            <input value={skills} onChange={(e) => setSkills(e.target.value)} />
          </label>
          <label>
            Interests (comma-separated)
            <input value={interests} onChange={(e) => setInterests(e.target.value)} />
          </label>
          <label>
            Hours per week
            <input
              type="number"
              min={1}
              max={168}
              value={hoursPerWeek}
              onChange={(e) => setHoursPerWeek(e.target.value)}
            />
          </label>
          <label>
            Weeks available
            <input
              type="number"
              min={1}
              max={104}
              value={weeksAvailable}
              onChange={(e) => setWeeksAvailable(e.target.value)}
            />
          </label>
          <label>
            Team size
            <input
              type="number"
              min={1}
              max={20}
              value={teamSize}
              onChange={(e) => setTeamSize(e.target.value)}
            />
          </label>
          <label>
            Compute tier
            <select
              value={compute}
              onChange={(e) => setCompute(e.target.value as ComputeTier)}
            >
              <option value="laptop">Laptop (CPU)</option>
              <option value="free_gpu">Free GPU (Colab/Kaggle)</option>
              <option value="paid">Paid GPU</option>
            </select>
          </label>
          <label>
            Goal
            <select value={goal} onChange={(e) => setGoal(e.target.value as GoalType)}>
              <option value="startup">Startup</option>
              <option value="portfolio">Portfolio</option>
              <option value="course_project">Course Project</option>
            </select>
          </label>
        </div>
        <button type="submit" className="primary">
          Save Profile
        </button>
      </form>
    </section>
  );
}
