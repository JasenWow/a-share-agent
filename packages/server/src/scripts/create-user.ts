import bcrypt from "bcryptjs"
import { db, sqlite } from "../db/connection"
import { users } from "../db/schema"
import { eq } from "drizzle-orm"

const args = process.argv.slice(2)
const name = args[0]
const email = args[1]
const password = args[2]
const isAdmin = args.includes("--admin")

if (!name || !email || !password) {
  console.log("Usage: bun run src/scripts/create-user.ts <name> <email> <password> [--admin]")
  process.exit(1)
}

async function main() {
  const existing = await db.select().from(users).where(eq(users.email, email)).get()

  if (existing) {
    // Update existing user
    const hashedPassword = await bcrypt.hash(password, 10)
    await db.update(users).set({
      name,
      password: hashedPassword,
      isAdmin,
    }).where(eq(users.email, email))
    console.log(`Updated user: ${email}`)
  } else {
    const hashedPassword = await bcrypt.hash(password, 10)
    await db.insert(users).values({ name, email, password: hashedPassword, isAdmin })
    console.log(`Created user: ${email} (admin: ${isAdmin})`)
  }
}

main()
  .then(() => {
    sqlite.close()
    process.exit(0)
  })
  .catch((err) => {
    console.error(err)
    sqlite.close()
    process.exit(1)
  })
