// The red message above the Login button for a failed login (axios error).
export const TOO_MANY_ATTEMPTS = "Too many failed login attempts. Please try again in 5 minutes.";

export function loginErrorMessage(error) {
  if (!error?.response) return "Can't reach the server. Please try again.";
  if (error.response.status === 401) return "Invalid username or password";
  if (error.response.status === 429) return TOO_MANY_ATTEMPTS;
  return "Something went wrong on the server. Please try again.";
}
