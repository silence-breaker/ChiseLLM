

final class build$_ {
def args = build_sc.args$
def scriptPath = """build.sc"""
/*<script>*/
import mill._
import mill.scalalib._

/**
 * ChiseLLM 项目 - Mill 构建配置
 * 
 * 这个配置文件帮助 IDE (如 VS Code + Metals) 正确识别 Chisel 依赖
 */
object chiselllm extends ScalaModule {
  def scalaVersion = "2.13.12"
  
  // Chisel 依赖
  def ivyDeps = Agg(
    ivy"org.chipsalliance::chisel:6.0.0"
  )
  
  // Scala 编译选项
  def scalacOptions = Seq(
    "-Xsource:2.13",
    "-language:reflectiveCalls",
    "-deprecation",
    "-feature",
    "-Xcheckinit",
    "-encoding", "utf-8"
  )
  
  // Chisel 编译器插件
  def scalacPluginIvyDeps = Agg(
    ivy"org.chipsalliance:::chisel-plugin:6.0.0"
  )
  
  // 源代码目录 (包含 tests/ 下的文件供 IDE 识别)
  override def millSourcePath = super.millSourcePath
  override def sources = T.sources(
    millSourcePath / "src",
    millSourcePath / "tests"
  )
}

/*</script>*/ /*<generated>*//*</generated>*/
}

object build_sc {
  private var args$opt0 = Option.empty[Array[String]]
  def args$set(args: Array[String]): Unit = {
    args$opt0 = Some(args)
  }
  def args$opt: Option[Array[String]] = args$opt0
  def args$: Array[String] = args$opt.getOrElse {
    sys.error("No arguments passed to this script")
  }

  lazy val script = new build$_

  def main(args: Array[String]): Unit = {
    args$set(args)
    val _ = script.hashCode() // hashCode to clear scalac warning about pure expression in statement position
  }
}

export build_sc.script as `build`

