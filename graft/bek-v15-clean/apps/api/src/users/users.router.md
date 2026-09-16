# bek-v15-clean/apps/api/src/users/users.router.ts

- UsersRouter · class · L10-L25 — class UsersRouter
- constructor · method · L11-L14 — constructor( @Inject(UsersService) private readonly users: UsersService, @Inject(AuthService) private readonly auth: AuthService, )
- me · method · L17-L19 — async me(@Ctx() ctx: AuthedTrpcContext)
- list · method · L22-L24 — async list()
