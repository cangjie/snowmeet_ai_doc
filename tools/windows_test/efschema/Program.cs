using Microsoft.EntityFrameworkCore;
using SnowmeetApi.Data;

// 只生成脚本，不连接数据库
var options = new DbContextOptionsBuilder<ApplicationDBContext>()
    .UseSqlServer("Server=localhost;Database=metadata_only;Trusted_Connection=True;TrustServerCertificate=True").Options;
using var db = new ApplicationDBContext(options);
File.WriteAllText(args[0], db.Database.GenerateCreateScript());
Console.WriteLine("written " + args[0]);
