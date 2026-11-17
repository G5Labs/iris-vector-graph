/// Fixture-only embedding provider for iteration 36 (W42); never part of the product.
/// It stands in for a %Embedding provider so Graph.KG.EmbedQueue.ProcessBatch can run on Community.
/// Text containing POISON makes the provider fail (as a provider outage or refusal would);
/// text containing EMPTY returns no vector; any other text gets a deterministic 768-wide vector.
Class W42.FixtureEmbedding Extends %Embedding.Interface
{

ClassMethod Embedding(input As %String, configuration As %String) As %Vector
{
    If input [ "POISON" { $$$ThrowStatus($$$ERROR($$$GeneralError, "W42 fixture provider refused the text")) }
    If input [ "EMPTY" { Quit "" }
    Set vec = ""
    For i = 1:1:768 { Set $Vector(vec, i, "double") = (i + $Length(input)) / 1000 }
    Quit vec
}

ClassMethod IsValidConfig(config As %DynamicObject, ByRef errorMsg As %String) As %Boolean
{
    Quit 1
}

}
