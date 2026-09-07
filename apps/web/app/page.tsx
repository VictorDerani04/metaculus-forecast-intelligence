type User = {
  id: string;
  email: string;
};

type HomeScreenProps = {
  user?: User | null;
};

export function HomeScreen({ user = null }: HomeScreenProps) {
  if (!user) {
    return (
      <main>
        <h1>Private Forecasting Workspace</h1>
        <p>Sign in to access your forecasting workspace.</p>
        <a href="/login">Sign in</a>
      </main>
    );
  }

  return (
    <main>
      <h1>Forecast Intelligence</h1>
      <p>{user.email}</p>
    </main>
  );
}

export default HomeScreen;
